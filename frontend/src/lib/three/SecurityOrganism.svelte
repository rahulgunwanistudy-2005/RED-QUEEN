<script>
  import { onMount, onDestroy } from "svelte";
  import * as THREE from "three";
  import { cinematicStep, cinemaMode } from "../store.js";

  export let width = "100%";
  export let height = "100%";
  export let interactive = true;

  let container;
  let renderer;
  let scene;
  let camera;
  let animId;
  let clock = new THREE.Clock();
  let webglAvailable = true;

  // Scene Objects
  let organismGroup;
  let coreMesh;
  let coreWire;
  let defenseRings = [];
  let agentNodes = [];
  let networkLines;
  let attackGroup;
  let verifierMesh;
  let barrierMesh;
  let breachVectorMesh;
  let shockwaveMesh;
  let shatterGroup;

  // Camera Choreography Targets (11 Narrative Beats)
  const CAMERA_POSES = [
    { pos: new THREE.Vector3(0, 1.2, 9.5), look: new THREE.Vector3(0, 0, 0) },        // 0. The attack evolves.
    { pos: new THREE.Vector3(1.8, 1.6, 8.8), look: new THREE.Vector3(0, 0.2, 0) },      // 1. So does the defense.
    { pos: new THREE.Vector3(-2.4, 1.0, 7.8), look: new THREE.Vector3(-0.6, 0, 0) },    // 2. Red//Queen doesn't wait.
    { pos: new THREE.Vector3(3.0, 3.2, 7.4), look: new THREE.Vector3(0.6, 0.3, 0) },    // 3. Manufactures next attack.
    { pos: new THREE.Vector3(-1.6, 0.6, 5.6), look: new THREE.Vector3(-0.4, 0.1, 0) },    // 4. Until one gets through.
    { pos: new THREE.Vector3(-0.6, 0.1, 4.2), look: new THREE.Vector3(-0.05, 0, 0) },   // 5. Bypass climax (Zoom in)
    { pos: new THREE.Vector3(2.2, 1.2, 6.2), look: new THREE.Vector3(1.6, 0.6, 0) },    // 6. Attacker does not certify.
    { pos: new THREE.Vector3(4.0, 1.6, 6.4), look: new THREE.Vector3(3.4, 1.3, 0) },    // 7. Independent verification.
    { pos: new THREE.Vector3(0, 2.6, 9.2), look: new THREE.Vector3(0, 0, 0) },        // 8. Change the boundary.
    { pos: new THREE.Vector3(0, 0.8, 7.2), look: new THREE.Vector3(0, 0, 0) },        // 9. Attack it again (Deflection).
    { pos: new THREE.Vector3(0, 1.2, 9.5), look: new THREE.Vector3(0, 0, 0) },        // 10. Closed. Proved.
  ];

  let currentCameraPos = new THREE.Vector3(0, 1.2, 9.5);
  let currentCameraLook = new THREE.Vector3(0, 0, 0);

  // Pointer & Raycaster State
  let mouse = new THREE.Vector2(-999, -999);
  let raycaster = new THREE.Raycaster();
  let hoveredObject = null;
  let hoveredData = null;

  // Parallax
  let targetRotX = 0;
  let targetRotY = 0;

  // Spatial HUD Screen Projections
  let hudPositions = {
    armor: { x: 120, y: 140, visible: true },
    gateway: { x: 140, y: 380, visible: true },
    agent: { x: 420, y: 180, visible: true },
    verifier: { x: 480, y: 320, visible: false },
    bypass: { x: 260, y: 240, visible: false },
  };

  // Preference for reduced motion
  let prefersReducedMotion = false;

  function checkWebGL() {
    try {
      const canvas = document.createElement("canvas");
      return !!(window.WebGLRenderingContext && (canvas.getContext("webgl") || canvas.getContext("experimental-webgl")));
    } catch {
      return false;
    }
  }

  function initThree() {
    if (!container) return;
    webglAvailable = checkWebGL();
    if (!webglAvailable) return;

    prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const w = container.clientWidth || 600;
    const h = container.clientHeight || 500;

    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0xFAF8F5, 0.02);

    camera = new THREE.PerspectiveCamera(40, w / h, 0.1, 100);
    camera.position.copy(CAMERA_POSES[0].pos);
    camera.lookAt(CAMERA_POSES[0].look);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    container.appendChild(renderer.domElement);

    organismGroup = new THREE.Group();
    scene.add(organismGroup);

    // 1. Central Core: ADK Agent Context
    const coreGeo = new THREE.IcosahedronGeometry(1.15, 1);
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0x141210,
      wireframe: true,
      transparent: true,
      opacity: 0.85,
    });
    coreWire = new THREE.Mesh(coreGeo, coreMat);
    coreWire.userData = {
      type: "core",
      name: "TARGET AGENT EXECUTION CONTEXT",
      component: "triage-agent (gemini-2.0-flash)",
      security: "Sandboxed ADK Ingress Boundary",
    };
    organismGroup.add(coreWire);

    const innerCoreGeo = new THREE.SphereGeometry(0.78, 24, 24);
    const innerCoreMat = new THREE.MeshStandardMaterial({
      color: 0x2A241D,
      roughness: 0.35,
      metalness: 0.85,
    });
    coreMesh = new THREE.Mesh(innerCoreGeo, innerCoreMat);
    organismGroup.add(coreMesh);

    // 2. Concentric Defense Rings (Model Armor, Gateway, IAM Boundaries)
    const ringSpecs = [
      { r: 1.85, color: 0x8B1E1E, label: "MODEL ARMOR PERIMETER", op: "deep_normalize" },
      { r: 2.6, color: 0x6B6458, label: "AGENT GATEWAY INGRESS", op: "geap.scan()" },
      { r: 3.3, color: 0x9C9486, label: "IAM CAPABILITY BOUNDARY", op: "Service Account Role" },
    ];

    ringSpecs.forEach((spec, idx) => {
      const ringGeo = new THREE.TorusGeometry(spec.r, 0.025, 16, 120);
      const ringMat = new THREE.MeshBasicMaterial({
        color: spec.color,
        transparent: true,
        opacity: 0.5 + idx * 0.15,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = Math.PI / 2 + (idx * 0.32);
      ring.rotation.y = idx * 0.22;
      ring.userData = {
        type: "defense",
        name: spec.label,
        component: "Google Cloud Model Armor",
        security: `Enforcing ${spec.op}`,
      };
      defenseRings.push(ring);
      organismGroup.add(ring);
    });

    // 3. Orbiting Agent Capability Nodes
    const agentTools = [
      { name: "read_ticket", color: 0x6B6458, radius: 2.3, speed: 0.75, yOff: 0.25, desc: "Benign Ticket Ingest" },
      { name: "run_privileged_fix", color: 0x8B1E1E, radius: 2.7, speed: -0.55, yOff: -0.35, desc: "Gated Maintenance Fix (Privileged)" },
      { name: "export_secrets", color: 0x1D4E75, radius: 3.1, speed: 0.45, yOff: 0.55, desc: "Exfiltration Canary Sink" },
    ];

    agentTools.forEach((tool) => {
      const nodeGeo = new THREE.OctahedronGeometry(0.2, 0);
      const nodeMat = new THREE.MeshStandardMaterial({
        color: tool.color,
        roughness: 0.3,
        metalness: 0.7,
      });
      const node = new THREE.Mesh(nodeGeo, nodeMat);
      node.userData = {
        type: "agent_tool",
        name: `TOOL: ${tool.name}`,
        component: "triage-agent Bound Capability",
        security: tool.desc,
        ...tool,
        angle: Math.random() * Math.PI * 2,
      };
      agentNodes.push(node);
      organismGroup.add(node);
    });

    // Network Lines connecting Nodes to Core
    const lineMat = new THREE.LineBasicMaterial({
      color: 0xC5BCAD,
      transparent: true,
      opacity: 0.4,
    });
    const lineGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(0, 0, 0),
    ]);
    networkLines = new THREE.LineSegments(lineGeo, lineMat);
    organismGroup.add(networkLines);

    // 4. Attack Particle Vectors
    attackGroup = new THREE.Group();
    organismGroup.add(attackGroup);

    // Shatter Particle Group (Deflection impact sparks)
    shatterGroup = new THREE.Group();
    organismGroup.add(shatterGroup);

    // 5. Independent Verifier Subsystem (Decoupled Orbiting Octahedron)
    const verifierGeo = new THREE.OctahedronGeometry(0.55, 0);
    const verifierMat = new THREE.MeshStandardMaterial({
      color: 0x1B5E3B,
      roughness: 0.15,
      metalness: 0.95,
      wireframe: true,
    });
    verifierMesh = new THREE.Mesh(verifierGeo, verifierMat);
    verifierMesh.position.set(4.2, 1.8, 0);
    verifierMesh.visible = false;
    verifierMesh.userData = {
      type: "verifier",
      name: "INDEPENDENT FIREWALLED VERIFIER",
      component: "sentinel.verifier.run Subprocess",
      security: "DB Role: sentinel_verifier (Access to Corpus: REVOKED)",
    };
    organismGroup.add(verifierMesh);

    // 6. Hardened Perimeter Barrier Mesh
    const barrierGeo = new THREE.SphereGeometry(2.35, 36, 18);
    const barrierMat = new THREE.MeshBasicMaterial({
      color: 0x1B5E3B,
      wireframe: true,
      transparent: true,
      opacity: 0.0,
    });
    barrierMesh = new THREE.Mesh(barrierGeo, barrierMat);
    organismGroup.add(barrierMesh);

    // 7. Persistent Breach Vector Line (Preserved as evidence in step 4/5)
    const breachGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-4.5, 0.2, 0.5),
      new THREE.Vector3(-1.8, 0.1, 0.2),
      new THREE.Vector3(0, 0, 0),
    ]);
    const breachMat = new THREE.LineBasicMaterial({
      color: 0x8B1E1E,
      linewidth: 3,
      transparent: true,
      opacity: 0.0,
    });
    breachVectorMesh = new THREE.Line(breachGeo, breachMat);
    organismGroup.add(breachVectorMesh);

    // 8. Dynamic Shockwave Ring
    const shockGeo = new THREE.RingGeometry(0.5, 0.65, 32);
    const shockMat = new THREE.MeshBasicMaterial({
      color: 0x8B1E1E,
      transparent: true,
      opacity: 0.0,
      side: THREE.DoubleSide,
    });
    shockwaveMesh = new THREE.Mesh(shockGeo, shockMat);
    shockwaveMesh.rotation.x = Math.PI / 2;
    organismGroup.add(shockwaveMesh);

    // Lights
    const ambLight = new THREE.AmbientLight(0xFFFFFF, 0.95);
    scene.add(ambLight);

    const dirLight = new THREE.DirectionalLight(0xFFFFFF, 1.3);
    dirLight.position.set(6, 9, 6);
    scene.add(dirLight);

    const redLight = new THREE.PointLight(0x8B1E1E, 3.0, 12);
    redLight.position.set(-5, -2, 3);
    scene.add(redLight);

    if (interactive) {
      window.addEventListener("mousemove", onMouseMove, { passive: true });
    }
    window.addEventListener("resize", onResize);

    animate();
  }

  function onMouseMove(e) {
    const rect = container?.getBoundingClientRect();
    if (!rect) return;
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    mouse.x = (clientX / rect.width) * 2 - 1;
    mouse.y = -(clientY / rect.height) * 2 - 1;

    targetRotY = mouse.x * 0.35;
    targetRotX = -mouse.y * 0.25;

    // Raycasting Hover Inspection
    if (camera && scene) {
      raycaster.setFromCamera(mouse, camera);
      const interactables = [coreWire, ...agentNodes, ...defenseRings, verifierMesh].filter(Boolean);
      const intersects = raycaster.intersectObjects(interactables);

      if (intersects.length > 0) {
        hoveredObject = intersects[0].object;
        hoveredData = hoveredObject.userData;
      } else {
        hoveredObject = null;
        hoveredData = null;
      }
    }
  }

  function onResize() {
    if (!container || !renderer || !camera) return;
    const w = container.clientWidth;
    const h = container.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }

  function updateSpatialHUD(w, h) {
    if (!camera || !container) return;

    function projectToScreen(vec3) {
      const v = vec3.clone();
      v.project(camera);
      return {
        x: (v.x * 0.5 + 0.5) * w,
        y: -(v.y * 0.5 - 0.5) * h,
      };
    }

    if (defenseRings[0]) {
      const p = projectToScreen(new THREE.Vector3(-1.8, 0.8, 0));
      hudPositions.armor = { x: p.x, y: p.y, visible: true };
    }
    if (defenseRings[1]) {
      const p = projectToScreen(new THREE.Vector3(0, -2.5, 0));
      hudPositions.gateway = { x: p.x, y: p.y, visible: true };
    }
    if (coreWire) {
      const p = projectToScreen(new THREE.Vector3(0, 1.4, 0));
      hudPositions.agent = { x: p.x, y: p.y, visible: true };
    }
    if (verifierMesh && verifierMesh.visible) {
      const p = projectToScreen(verifierMesh.position);
      hudPositions.verifier = { x: p.x, y: p.y, visible: true };
    } else {
      hudPositions.verifier.visible = false;
    }
    if ($cinematicStep === 5) {
      const p = projectToScreen(new THREE.Vector3(-0.6, 0.1, 0));
      hudPositions.bypass = { x: p.x, y: p.y, visible: true };
    } else {
      hudPositions.bypass.visible = false;
    }
  }

  function triggerShatterSparks(pos) {
    if (!shatterGroup) return;
    for (let i = 0; i < 8; i++) {
      const sparkGeo = new THREE.SphereGeometry(0.04, 6, 6);
      const sparkMat = new THREE.MeshBasicMaterial({
        color: 0x207A4C,
        transparent: true,
        opacity: 1.0,
      });
      const spark = new THREE.Mesh(sparkGeo, sparkMat);
      spark.position.copy(pos);
      spark.userData = {
        vel: new THREE.Vector3(
          (Math.random() - 0.5) * 4,
          (Math.random() - 0.5) * 4,
          (Math.random() - 0.5) * 4
        ),
      };
      shatterGroup.add(spark);
    }
  }

  function updateNarrativeState(step, time, dt) {
    if (!organismGroup) return;

    // Smooth Camera Choreography to Pose Target
    const targetPose = CAMERA_POSES[Math.min(step, CAMERA_POSES.length - 1)];
    const easeFactor = prefersReducedMotion ? 0.25 : ($cinemaMode ? 0.06 : 0.045);

    currentCameraPos.lerp(targetPose.pos, easeFactor);
    currentCameraLook.lerp(targetPose.look, easeFactor);
    camera.position.copy(currentCameraPos);
    camera.lookAt(currentCameraLook);

    // Step-Specific Geometry & Material Behavior (11 Steps)
    if (step === 0) {
      coreWire.material.color.setHex(0x141210);
      coreMesh.material.color.setHex(0x2A241D);
      barrierMesh.material.opacity = 0.0;
      verifierMesh.visible = false;
      breachVectorMesh.material.opacity = 0.0;
      shockwaveMesh.material.opacity = 0.0;
      defenseRings[0].material.color.setHex(0x8B1E1E);
    } else if (step === 1) {
      defenseRings.forEach((r, i) => {
        r.rotation.z += 0.015 * (i + 1);
      });
      barrierMesh.material.opacity = 0.05;
      verifierMesh.visible = false;
      breachVectorMesh.material.opacity = 0.0;
    } else if (step === 2) {
      defenseRings[0].material.color.setHex(0x8B1E1E);
      barrierMesh.material.opacity = 0.0;
      verifierMesh.visible = false;
      breachVectorMesh.material.opacity = 0.0;
    } else if (step === 3) {
      defenseRings.forEach((r) => (r.rotation.y += 0.025));
      verifierMesh.visible = false;
      breachVectorMesh.material.opacity = 0.0;
    } else if (step === 4) {
      // Step 4: Approaching breach
      defenseRings[0].material.color.setHex(0x8B1E1E);
      breachVectorMesh.material.opacity = 0.5;
      verifierMesh.visible = false;
    } else if (step === 5) {
      // Step 5: Climax: Breach confirmed!
      coreWire.material.color.setHex(0x8B1E1E);
      coreMesh.material.color.setHex(0x9E1F1F);
      verifierMesh.visible = false;
      breachVectorMesh.material.opacity = 1.0;
      
      // Shockwave pulse
      shockwaveMesh.scale.addScalar(0.08);
      if (shockwaveMesh.scale.x > 3.5) shockwaveMesh.scale.set(1, 1, 1);
      shockwaveMesh.material.opacity = 0.7;
    } else if (step === 6) {
      // Step 6: Attacker does not certify the fix
      coreWire.material.color.setHex(0x8B1E1E);
      verifierMesh.visible = true;
      verifierMesh.rotation.y += 0.03;
      breachVectorMesh.material.opacity = 0.6;
      shockwaveMesh.material.opacity = 0.0;
    } else if (step === 7) {
      // Step 7: Independent Verifier decoupled and active
      verifierMesh.visible = true;
      verifierMesh.rotation.y += 0.04;
      verifierMesh.rotation.x += 0.025;
      breachVectorMesh.material.opacity = 0.3;
    } else if (step === 8) {
      // Step 8: Hardening: Barrier projected, defense contracted
      barrierMesh.material.opacity = 0.5;
      barrierMesh.material.color.setHex(0x1B5E3B);
      verifierMesh.visible = true;
      breachVectorMesh.material.opacity = 0.0;
    } else if (step === 9) {
      // Step 9: Re-Test: particles colliding and shattering
      barrierMesh.material.opacity = 0.75;
      barrierMesh.material.color.setHex(0x1B5E3B);
      verifierMesh.visible = true;
      breachVectorMesh.material.opacity = 0.0;
    } else if (step >= 10) {
      // Step 10: Closed. Proved. (Stable verified green)
      barrierMesh.material.opacity = 0.8;
      barrierMesh.material.color.setHex(0x1B5E3B);
      coreWire.material.color.setHex(0x1B5E3B);
      coreMesh.material.color.setHex(0x1D4E75);
      verifierMesh.visible = true;
      breachVectorMesh.material.opacity = 0.0;
    }
  }

  function animate() {
    animId = requestAnimationFrame(animate);
    const dt = clock.getDelta();
    const time = clock.getElapsedTime();
    const w = container?.clientWidth || 600;
    const h = container?.clientHeight || 500;

    // Smooth Parallax
    if (!prefersReducedMotion) {
      organismGroup.rotation.y += (targetRotY - organismGroup.rotation.y) * 0.05 + 0.0018;
      organismGroup.rotation.x += (targetRotX - organismGroup.rotation.x) * 0.05;
    }

    // Core subtle breathing pulse
    const pulse = 1 + Math.sin(time * 1.8) * ($cinematicStep === 5 ? 0.08 : 0.03);
    coreWire.scale.set(pulse, pulse, pulse);
    coreWire.rotation.y += ($cinematicStep === 5 ? 0.015 : 0.004);

    // Concentric rings oscillation
    defenseRings.forEach((ring, idx) => {
      ring.rotation.z += 0.003 * (idx % 2 === 0 ? 1 : -1);
    });

    // Orbiting agent capability nodes
    const networkPoints = [];
    agentNodes.forEach((node) => {
      const { radius, speed, yOff } = node.userData;
      node.userData.angle += dt * speed;
      const a = node.userData.angle;
      node.position.set(Math.cos(a) * radius, yOff + Math.sin(a * 2) * 0.22, Math.sin(a) * radius);
      node.rotation.x += 0.015;
      node.rotation.y += 0.02;

      networkPoints.push(new THREE.Vector3(0, 0, 0));
      networkPoints.push(node.position.clone());
    });

    if (networkLines) {
      networkLines.geometry.setFromPoints(networkPoints);
    }

    // Attack Particle Injection
    const maxParticles = prefersReducedMotion ? 6 : ($cinematicStep === 3 ? 24 : 16);
    if (attackGroup.children.length < maxParticles && $cinematicStep >= 2) {
      const atkGeo = new THREE.SphereGeometry(0.065, 8, 8);
      const atkMat = new THREE.MeshBasicMaterial({
        color: 0x8B1E1E,
        transparent: true,
        opacity: 0.95,
      });
      const atk = new THREE.Mesh(atkGeo, atkMat);
      const spawnAngle = Math.random() * Math.PI * 2;
      const spawnRadius = 4.8 + Math.random() * 1.6;
      atk.position.set(
        Math.cos(spawnAngle) * spawnRadius,
        (Math.random() - 0.5) * 2.2,
        Math.sin(spawnAngle) * spawnRadius
      );
      atk.userData = {
        speed: 0.9 + Math.random() * 1.3,
        target: new THREE.Vector3(0, 0, 0),
      };
      attackGroup.add(atk);
    }

    // Attack particle physics
    for (let i = attackGroup.children.length - 1; i >= 0; i--) {
      const atk = attackGroup.children[i];
      const dir = new THREE.Vector3().subVectors(atk.userData.target, atk.position).normalize();
      atk.position.addScaledVector(dir, dt * atk.userData.speed * ($cinematicStep === 5 ? 0.35 : 1.0)); // Time dilation on breach!

      const dist = atk.position.length();

      // Step >= 8 (Hardened barrier blocks particles and creates sparks)
      if ($cinematicStep >= 8 && dist < 2.35) {
        triggerShatterSparks(atk.position);
        atk.position.addScaledVector(dir, -0.3);
        atk.material.opacity -= dt * 4.0;
        if (atk.material.opacity <= 0.05) {
          attackGroup.remove(atk);
          atk.geometry.dispose();
          atk.material.dispose();
        }
      } else if (dist < 1.15) {
        attackGroup.remove(atk);
        atk.geometry.dispose();
        atk.material.dispose();
      }
    }

    // Shatter sparks physics
    for (let i = shatterGroup.children.length - 1; i >= 0; i--) {
      const spark = shatterGroup.children[i];
      spark.position.addScaledVector(spark.userData.vel, dt);
      spark.material.opacity -= dt * 2.5;
      if (spark.material.opacity <= 0.05) {
        shatterGroup.remove(spark);
        spark.geometry.dispose();
        spark.material.dispose();
      }
    }

    updateNarrativeState($cinematicStep, time, dt);
    updateSpatialHUD(w, h);

    renderer.render(scene, camera);
  }

  $: if ($cinematicStep != null && clock) {
    updateNarrativeState($cinematicStep, clock.getElapsedTime(), 0.016);
  }

  onMount(() => {
    initThree();
  });

  onDestroy(() => {
    if (animId) cancelAnimationFrame(animId);
    if (interactive) {
      window.removeEventListener("mousemove", onMouseMove);
    }
    window.removeEventListener("resize", onResize);

    if (renderer) {
      renderer.dispose();
      if (renderer.domElement && renderer.domElement.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
    }
  });
</script>

<div
  class="three-container"
  bind:this={container}
  style="width: {width}; height: {height};"
>
  {#if !webglAvailable}
    <!-- Graceful WebGL Fallback -->
    <div class="webgl-fallback">
      <div class="fallback-icon">🛡</div>
      <div class="fallback-title serif-display">RED//QUEEN SECURITY ORGANISM</div>
      <div class="fallback-desc mono">
        Model Armor Perimeter · Agent Gateway · Isolated Subprocess Verifier
      </div>
    </div>
  {:else}
    <!-- Contextual Projected Spatial HUD Labels -->
    {#if hudPositions.armor.visible}
      <div
        class="spatial-hud-tag mono"
        style="transform: translate3d({hudPositions.armor.x}px, {hudPositions.armor.y}px, 0);"
      >
        <span class="hud-dot dot-oxblood"></span>
        <span class="hud-text">MODEL ARMOR / PERIMETER</span>
      </div>
    {/if}

    {#if hudPositions.gateway.visible}
      <div
        class="spatial-hud-tag mono"
        style="transform: translate3d({hudPositions.gateway.x}px, {hudPositions.gateway.y}px, 0);"
      >
        <span class="hud-dot dot-blue"></span>
        <span class="hud-text">AGENT GATEWAY (ADK)</span>
      </div>
    {/if}

    {#if hudPositions.agent.visible}
      <div
        class="spatial-hud-tag mono"
        style="transform: translate3d({hudPositions.agent.x}px, {hudPositions.agent.y}px, 0);"
      >
        <span class="hud-dot dot-stone"></span>
        <span class="hud-text">TRIAGE-AGENT CORE</span>
      </div>
    {/if}

    {#if hudPositions.verifier.visible}
      <div
        class="spatial-hud-tag hud-verifier mono"
        style="transform: translate3d({hudPositions.verifier.x}px, {hudPositions.verifier.y}px, 0);"
      >
        <span class="hud-dot dot-green"></span>
        <span class="hud-text">INDEPENDENT VERIFIER (sentinel_verifier)</span>
      </div>
    {/if}

    {#if hudPositions.bypass.visible}
      <div
        class="spatial-hud-tag hud-bypass mono"
        style="transform: translate3d({hudPositions.bypass.x}px, {hudPositions.bypass.y}px, 0);"
      >
        <span class="hud-dot dot-oxblood pulse-dot"></span>
        <span class="hud-text">⚠ BYPASS BREACH POINT // EXPLOIT DETECTED</span>
      </div>
    {/if}

    <!-- Raycasting Node Hover Tooltip Inspector -->
    {#if hoveredData}
      <div class="raycast-tooltip panel mono">
        <div class="rt-title serif-display">{hoveredData.name}</div>
        <div class="rt-comp">{hoveredData.component}</div>
        <div class="rt-sec">{hoveredData.security}</div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .three-container {
    position: relative;
    width: 100%;
    height: 100%;
    min-height: 520px;
    overflow: hidden;
    cursor: grab;
  }
  .three-container:active {
    cursor: grabbing;
  }

  .spatial-hud-tag {
    position: absolute;
    top: 0;
    left: 0;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.94);
    backdrop-filter: blur(8px);
    border: 1px solid var(--border);
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 9.5px;
    font-weight: 800;
    letter-spacing: 0.08em;
    color: var(--text);
    pointer-events: none;
    transition: transform 0.08s ease-out;
    box-shadow: var(--shadow-card);
    white-space: nowrap;
    z-index: 10;
  }

  .hud-verifier {
    background: var(--verif-green-dim);
    border-color: rgba(27, 94, 59, 0.4);
    color: var(--verif-green);
  }

  .hud-bypass {
    background: var(--oxblood-dim);
    border-color: var(--oxblood);
    color: var(--oxblood);
    box-shadow: 0 0 14px rgba(139, 30, 30, 0.35);
  }

  .hud-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }
  .dot-oxblood { background: var(--oxblood); box-shadow: 0 0 6px var(--oxblood); }
  .dot-blue { background: var(--tech-blue); }
  .dot-stone { background: var(--stone); }
  .dot-green { background: var(--verif-green); box-shadow: 0 0 6px var(--verif-green); }

  .pulse-dot {
    animation: pulse 1s infinite;
  }

  .raycast-tooltip {
    position: absolute;
    bottom: 18px;
    left: 18px;
    background: #FFFFFF;
    color: var(--text);
    border: 1.5px solid var(--oxblood);
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 11px;
    box-shadow: var(--shadow-elevated);
    pointer-events: none;
    z-index: 20;
    animation: fadeIn 0.15s ease;
  }
  .rt-title {
    font-size: 13.5px;
    font-weight: 900;
    color: var(--text);
    letter-spacing: 0.04em;
    margin-bottom: 2px;
  }
  .rt-comp {
    color: var(--oxblood);
    font-size: 11px;
    font-weight: 800;
    margin-bottom: 2px;
  }
  .rt-sec {
    color: var(--text-dim);
    font-size: 10.5px;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .webgl-fallback {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    text-align: center;
    padding: 40px;
    background: var(--bg-subtle);
    border: 1px solid var(--border);
  }
  .fallback-icon { font-size: 48px; margin-bottom: 12px; }
  .fallback-title { font-size: 20px; font-weight: 900; }
  .fallback-desc { font-size: 12px; color: var(--stone); margin-top: 6px; }
</style>
