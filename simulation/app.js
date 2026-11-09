(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const clamp = (x, a, b) => Math.min(Math.max(x, a), b);
  const lerp = (a, b, f) => a + (b - a) * f;
  const ease = (f) => f * f * (3 - 2 * f);
  const fmtClock = (s) => { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };

  const DESIGN = { rpm: 1600, flow_lpm: 2.0, T_C: 30, Tc_C: 10, pH: 4.5, gas_gNm3: 300, gas_Nlpm: 1.0, cover: 'offgas', resist_um: 1.0, line_m: 1.0, line_mm: 4, open: false };
  const OPEN = { rpm: 500, flow_lpm: 1.5, T_C: 25, Tc_C: 25, pH: 5.6, gas_gNm3: 200, gas_Nlpm: 2.0, cover: 'air', resist_um: 1.0, line_m: 5.0, line_mm: 6, open: true };
  let settings = Object.assign({}, DESIGN);
  let sim = null, steps = [], total = 1, procT = 0, playing = true, speed = 10, firstResult = true;

  const PARTS = [
    [1, 'Deck plate', 'Aluminium, PVDF-covered', 'Carries the module; the motor hangs below it.'],
    [2, 'Enclosure', 'PVDF panels, purged with about 10 m³/h', 'Holds any leak; an ozone monitor trips an interlock.'],
    [3, 'Direct-drive motor', 'Hollow-shaft torque motor, encoder, rotary union', 'Spins the chuck up to 3000 rpm with no belt.'],
    [4, 'Vacuum chuck', 'PVDF on 316L steel', 'Holds the wafer by vacuum through the hollow shaft.'],
    [5, 'Wafer', '300 mm silicon with resist', 'The colour shows the resist left; it clears from the centre outward.'],
    [6, 'Labyrinth seal', 'PVDF collar, 316L skirt, nitrogen-purged', 'Keeps ozone water out of the drive with no rubbing seal.'],
    [7, 'Rim collector', 'PVDF, turned and welded', 'Water runs under the drip lip into the gutter and two drains; gas rises into the plenum and two ports.'],
    [8, 'Quartz lid', 'Fused quartz, 340 by 12 mm', 'Sits 3 mm above the wafer while stripping and holds the off-gas over the film. Lets UV through.'],
    [9, 'Carrier ring, rods, lift plate', 'PVDF ring, 316L rods', 'Lift the lid 60 mm for the wafer change. The ring is heated so no water condenses on the quartz.'],
    [10, 'Lift cylinders', 'Pneumatic, three', 'Raise and lower the lid assembly.'],
    [11, 'Coaxial dispenser', '1/4 in PFA core in a 20 mm PFA sleeve', 'Ozone water down the core, off-gas down the ring around it.'],
    [12, 'UV source (option)', 'UVC LED tiles or 222 nm lamps', 'For a crust step, with oxygen in the gap instead of the off-gas.'],
    [13, 'Heat-recovery exchanger', 'PFA tube in tube', 'The warm drain heats the cold ozone water by about 12 K.'],
  ];
  const ANCHOR = { 1: [-220, -120, -30], 2: [-262, 240, -200], 3: [0, -215, -118], 4: [70, -12, 0], 5: [-130, 0.5, 0], 6: [0, -45, -48],
    7: [212, -40, 0], 8: [125, 10, 0], 9: [0, 100, -150], 10: [0, 268, -150], 11: [0, 215, -10], 12: [-120, 48, 0], 13: [330, -240, 120] };
  const LIFTED = { 8: 1, 9: 1, 11: 1, 12: 1 };

  // ------------------------------------------------------------------ renderer and scene
  const stageEl = $('#stage'), viewEl = $('#viewport'), canvas = $('#view');
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  } catch (e) {
    const d = document.createElement('div'); d.className = 'nogl';
    d.textContent = 'This browser cannot show 3D (WebGL is off). The readouts and charts on the right still work.';
    viewEl.appendChild(d);
  }
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1.6, 5, 9000);
  camera.position.set(-720, 470, 1180);
  let controls = null;
  if (renderer) {
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.localClippingEnabled = true;
    controls = new THREE.OrbitControls(camera, canvas);
    controls.enableDamping = true; controls.dampingFactor = 0.08;
    controls.minDistance = 60; controls.maxDistance = 2600;
    controls.target.set(70, -20, 0);
  }
  scene.add(new THREE.HemisphereLight(0xffffff, 0x7b8894, 0.9));
  const key = new THREE.DirectionalLight(0xffffff, 0.75); key.position.set(420, 760, 520); scene.add(key);
  const fill = new THREE.DirectionalLight(0xffffff, 0.3); fill.position.set(-520, 180, -340); scene.add(fill);
  const rim = new THREE.DirectionalLight(0xffffff, 0.25); rim.position.set(0, -300, 600); scene.add(rim);

  const cutPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
  let cutOn = true;
  const clipMats = [];
  function M(opts, clip) {
    const m = new THREE.MeshStandardMaterial(Object.assign({ side: THREE.DoubleSide, roughness: 0.55, metalness: 0.05 }, opts));
    if (clip !== false) { clipMats.push(m); m.clippingPlanes = [cutPlane]; }
    return m;
  }
  function applyCut() {
    for (const m of clipMats) { m.clippingPlanes = cutOn ? [cutPlane] : []; m.needsUpdate = true; }
    for (const g of capGroups) g.visible = cutOn;
    for (const m of movingCaps) m.visible = cutOn;
  }
  const MAT = {
    pvdf: { color: 0xded4bf, roughness: 0.62 },
    pvdfDark: { color: 0xc9bea6, roughness: 0.62 },
    alu: { color: 0xb4bbc2, roughness: 0.42, metalness: 0.3 },
    steel: { color: 0x9fa7ae, roughness: 0.36, metalness: 0.4 },
    motor: { color: 0x39424a, roughness: 0.5, metalness: 0.3 },
    quartz: { color: 0xb9dcf3, roughness: 0.06, metalness: 0.0, transparent: true, opacity: 0.38, depthWrite: false },
    pfa: { color: 0xf2f4f4, roughness: 0.4, transparent: true, opacity: 0.9 },
    uv: { color: 0x2c3339, roughness: 0.5, metalness: 0.25 },
    encl: { color: 0xc4cbd0, roughness: 0.7, transparent: true, opacity: 0.1, depthWrite: false },
    silicon: { color: 0x5a6670, roughness: 0.3, metalness: 0.35 },
  };

  function latheSharp(profile, seg) {
    seg = seg || 96;
    const pos = [], nor = [], idx = [];
    const P = profile.concat([profile[0]]);
    for (let e = 0; e < P.length - 1; e++) {
      const r1 = P[e][0], y1 = P[e][1], r2 = P[e + 1][0], y2 = P[e + 1][1];
      const dr = r2 - r1, dy = y2 - y1, L = Math.hypot(dr, dy) || 1;
      const nr = dy / L, ny = -dr / L;
      const base = pos.length / 3;
      for (let s = 0; s <= seg; s++) {
        const a = 2 * Math.PI * s / seg, ca = Math.cos(a), sa = Math.sin(a);
        pos.push(r1 * ca, y1, -r1 * sa, r2 * ca, y2, -r2 * sa);
        nor.push(nr * ca, ny, -nr * sa, nr * ca, ny, -nr * sa);
      }
      for (let s = 0; s < seg; s++) { const i = base + 2 * s; idx.push(i, i + 2, i + 1, i + 1, i + 2, i + 3); }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
    g.setIndex(idx);
    return g;
  }
  const ring = (r1, r2, y1, y2) => [[r1, y1], [r2, y1], [r2, y2], [r1, y2]];

  const partMeshes = {}, pickables = [];
  function turned(parent, profile, kind, part, opts, seg) {
    opts = opts || {};
    const mesh = add(parent, latheSharp(profile, seg), MAT[kind], part, opts);
    if (opts.cap !== false && opts.clip !== false) {
      const at = opts.at || [0, 0, 0];
      if (Math.abs(at[2]) < 1e-6) {
        const g = parent === rotor ? capsG : (parent === lidParts || parent === lidG ? (opts.capInto || parent) : capsG);
        const before = g.children.length;
        addCap(g, profile.map(([r, y]) => [r, y + (at[1] || 0)]), kind, at[0]);
        if (g !== capsG) for (let i = before; i < g.children.length; i++) movingCaps.push(g.children[i]);
      }
    }
    return mesh;
  }
  function add(parent, geo, mat, part, opts) {
    opts = opts || {};
    const mesh = new THREE.Mesh(geo, M(mat, opts.clip));
    mesh.userData.part = part;
    if (opts.at) mesh.position.set(opts.at[0], opts.at[1] || 0, opts.at[2]);
    parent.add(mesh);
    (partMeshes[part] = partMeshes[part] || []).push(mesh);
    if (opts.pick !== false) pickables.push(mesh);
    return mesh;
  }

  // section caps: the cut face of every turned part is its own profile, drawn flat on the cut plane
  const capGroups = [], movingCaps = [];
  const CAPC = { pvdf: 0xcbbd9c, pvdfDark: 0xb3a586, alu: 0x8e979f, steel: 0x7d8790, motor: 0x262d33, quartz: 0xa9d0ec, pfa: 0xd5dde1, uv: 0x1d2328, silicon: 0x38424a };
  const capMats = {};
  function capMat(kind) {
    if (!capMats[kind]) capMats[kind] = new THREE.MeshBasicMaterial({ color: CAPC[kind], side: THREE.DoubleSide, transparent: kind === 'quartz', opacity: kind === 'quartz' ? 0.8 : 1 });
    return capMats[kind];
  }
  function capShape(pts) { const sh = new THREE.Shape(); pts.forEach(([x, y], i) => (i ? sh.lineTo(x, y) : sh.moveTo(x, y))); return new THREE.ShapeGeometry(sh); }
  function addCap(group, profile, kind, cx) {
    cx = cx || 0;
    for (const sgn of [1, -1]) {
      const m = new THREE.Mesh(capShape(profile.map(([r, y]) => [cx + sgn * r, y])), capMat(kind));
      m.position.z = -0.05; group.add(m);
    }
  }
  const root = new THREE.Group(); scene.add(root);
  const rotor = new THREE.Group(); scene.add(rotor);
  const waferG = new THREE.Group(); scene.add(waferG);
  const lidG = new THREE.Group(); scene.add(lidG);
  const lidParts = new THREE.Group(); lidG.add(lidParts);
  const cylG = new THREE.Group(); scene.add(cylG);
  const enclG = new THREE.Group(); scene.add(enclG);
  const capsG = new THREE.Group(); scene.add(capsG); capGroups.push(capsG);
  const secG = new THREE.Group(); scene.add(secG); capGroups.push(secG);

  // 1 deck plate (with the opening for the motor)
  {
    const sh = new THREE.Shape();
    sh.moveTo(-270, -270); sh.lineTo(430, -270); sh.lineTo(430, 270); sh.lineTo(-270, 270); sh.lineTo(-270, -270);
    const hole = new THREE.Path(); hole.absarc(0, 0, 120, 0, Math.PI * 2, true); sh.holes.push(hole);
    const g = new THREE.ExtrudeGeometry(sh, { depth: 15, bevelEnabled: false, curveSegments: 64 });
    g.rotateX(-Math.PI / 2);
    add(root, g, MAT.alu, 1, { at: [0, -135, 0] });
    for (const [x0, x1] of [[-270, -120], [120, 430]]) { const m = new THREE.Mesh(capShape([[x0, -135], [x1, -135], [x1, -120], [x0, -120]]), capMat('alu')); m.position.z = -0.05; capsG.add(m); }
  }
  // 2 enclosure: PVDF panels with a slot on the left for the wafer
  {
    const H = 420, y0 = -120;
    const box = (w, h, d, x, y, z) => { const m = add(enclG, new THREE.BoxGeometry(w, h, d), MAT.encl, 2, { pick: false }); m.position.set(x, y, z); return m; };
    box(540, H, 10, 0, y0 + H / 2, -265);
    box(540, H, 10, 0, y0 + H / 2, 265);
    box(10, H, 540, 265, y0 + H / 2, 0);
    box(10, 135, 540, -265, y0 + 135 / 2, 0);                 // left wall below the slot
    box(10, H - 175, 540, -265, y0 + 175 + (H - 175) / 2, 0);    // left wall above the slot (slot from y 15 to 55)
    box(540, 10, 540, 0, 295, 0);
  }
  // 3 motor, flange, rotary union
  turned(root, ring(35, 115, -270, -150), 'motor', 3);
  turned(root, ring(40, 130, -150, -120), 'motor', 3);
  turned(root, ring(0, 30, -305, -270), 'steel', 3, {}, 48);
  // 4 chuck and hollow shaft (rotate)
  turned(rotor, ring(0, 100, -20.8, -0.9), 'pvdfDark', 4);
  turned(rotor, ring(14, 20, -160, -20.8), 'steel', 4, {}, 48);
  // 6 labyrinth: fixed collar, rotating skirt
  turned(root, ring(29, 35, -82, -40), 'pvdf', 6, {}, 64);
  turned(rotor, ring(42, 48, -60, -26), 'steel', 6, {}, 64);
  // 7 rim collector, drip lip, gas ports, drains
  turned(root, [[160, -20], [160, -90], [40, -90], [40, -98], [213, -98], [213, 36], [172, 36], [172, 30], [205, 30], [205, -90], [168, -90], [168, -20]], 'pvdf', 7, {}, 128);
  turned(root, [[205, 24], [205, 18], [185, 9], [183, 13]], 'pvdf', 7, {}, 128);
  for (const sx of [1, -1]) turned(root, ring(7, 9, 36, 72), 'pvdf', 7, { at: [195 * sx, 0, 0] }, 32);
  for (const sz of [1, -1]) add(root, latheSharp(ring(9, 11, -182, -98), 32), MAT.pvdf, 7, { at: [0, 0, 190 * sz] });
  // 13 heat exchanger under the deck (not cut, as in the CAD drawing)
  for (let k = 0; k < 6; k++) add(root, latheSharp(ring(56, 70, -182 - 26 * k, -166 - 26 * k), 48), MAT.pfa, 13, { at: [330, 0, 120], clip: false });
  // 5 wafer: body, plus a polar top surface whose colours show the resist
  const K = 90, MS = 128;
  function polarDisc(R) {
    const pos = [], uv = [], col = [], nor = [], idx = [];
    for (let k = 0; k <= K; k++) {
      const r = R * k / K;
      for (let s = 0; s <= MS; s++) {
        const a = 2 * Math.PI * s / MS, x = r * Math.cos(a), z = -r * Math.sin(a);
        pos.push(x, 0, z); uv.push(0.5 + x / (2 * R), 0.5 - z / (2 * R)); col.push(1, 1, 1); nor.push(0, 1, 0);
      }
    }
    for (let k = 0; k < K; k++) for (let s = 0; s < MS; s++) {
      const i = k * (MS + 1) + s, j = i + MS + 1;
      idx.push(i, j, i + 1, i + 1, j, j + 1);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    g.setIndex(idx);
    return g;
  }
  function waferTexture() {
    const c = document.createElement('canvas'); c.width = c.height = 1024;
    const g = c.getContext('2d'), px = 1024 / 300;
    const grad = g.createLinearGradient(0, 0, 1024, 1024);
    grad.addColorStop(0, '#b9c3cc'); grad.addColorStop(0.5, '#a3aeb8'); grad.addColorStop(1, '#bfc8d0');
    g.fillStyle = grad; g.fillRect(0, 0, 1024, 1024);
    const die = 22 * px, off = 512 % die;
    g.strokeStyle = 'rgba(40, 52, 64, 0.55)'; g.lineWidth = 2;
    for (let x = off; x < 1024; x += die) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, 1024); g.stroke(); }
    for (let y = off; y < 1024; y += die) { g.beginPath(); g.moveTo(0, y); g.lineTo(1024, y); g.stroke(); }
    g.strokeStyle = 'rgba(255, 255, 255, 0.55)'; g.lineWidth = 3 * px;      // edge exclusion
    g.beginPath(); g.arc(512, 512, 512 - 1.5 * px, 0, Math.PI * 2); g.stroke();
    g.fillStyle = '#4a555e'; g.beginPath(); g.moveTo(512 - 6, 1024); g.lineTo(512, 1024 - 10); g.lineTo(512 + 6, 1024); g.fill();
    const t = new THREE.CanvasTexture(c); t.anisotropy = 4;
    return t;
  }
  turned(waferG, ring(0, 150, -0.8, -0.08), 'silicon', 5, { cap: false }, 128);
  addCap(secG, ring(0, 150, -0.8, 0), 'silicon');
  const waferTopGeo = polarDisc(150);
  const waferTop = add(waferG, waferTopGeo, { color: 0xffffff, roughness: 0.32, metalness: 0.2, vertexColors: true, map: waferTexture() }, 5);
  // liquid film (vertex colours: dissolved ozone; height: film thickness, drawn 50 times thicker)
  const filmGeo = polarDisc(150);
  const filmMesh = new THREE.Mesh(filmGeo, M({ color: 0xffffff, roughness: 0.12, metalness: 0.0, vertexColors: true, transparent: true, opacity: 0.55, depthWrite: false }));
  filmMesh.renderOrder = 2;
  waferG.add(filmMesh);
  // section of the resist (drawn 0.6 mm thick) and of the film, on the cut plane
  function stripGeo() {
    const g = new THREE.BufferGeometry(), n = 2 * (K + 1) * 2;
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(n * 3).fill(1), 3));
    const idx = [];
    for (const half of [0, 1]) {
      const b = half * 2 * (K + 1);
      for (let k = 0; k < K; k++) { const i = b + 2 * k; idx.push(i, i + 2, i + 1, i + 1, i + 2, i + 3); }
    }
    g.setIndex(idx);
    return g;
  }
  const resistSec = new THREE.Mesh(stripGeo(), new THREE.MeshBasicMaterial({ color: 0xe0802a, side: THREE.DoubleSide }));
  const filmSec = new THREE.Mesh(stripGeo(), new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide, transparent: true, opacity: 0.85 }));
  resistSec.position.z = -0.04; filmSec.position.z = -0.03;
  secG.add(resistSec); secG.add(filmSec);
  function setStrip(mesh, lowFn, highFn, colFn) {
    const pos = mesh.geometry.attributes.position.array, col = mesh.geometry.attributes.color.array;
    for (const half of [0, 1]) {
      const sg = half ? -1 : 1, b = half * 2 * (K + 1);
      for (let k = 0; k <= K; k++) {
        const r = 150 * k / K, i = 3 * (b + 2 * k);
        pos[i] = sg * r; pos[i + 1] = lowFn(k); pos[i + 2] = 0;
        pos[i + 3] = sg * r; pos[i + 4] = highFn(k); pos[i + 5] = 0;
        if (colFn) { const c = colFn(k); col[i] = col[i + 3] = c.r; col[i + 1] = col[i + 4] = c.g; col[i + 2] = col[i + 5] = c.b; }
      }
    }
    mesh.geometry.attributes.position.needsUpdate = true;
    if (colFn) mesh.geometry.attributes.color.needsUpdate = true;
  }
  const resistTop = new Float32Array(K + 1);
  // 8 lid, 9 carrier ring rods plate, 11 dispenser, 12 UV option (all move with the lift)
  const lidMesh = turned(lidParts, ring(11, 170, 3, 15), 'quartz', 8, {}, 128); lidMesh.renderOrder = 3;
  {
    const lm = new THREE.LineBasicMaterial({ color: 0x3f7fb3, transparent: true, opacity: 0.8 }); clipMats.push(lm); lm.clippingPlanes = [cutPlane];
    const pts = [];
    for (const [rr, yy] of [[170, 3], [170, 15], [11, 3], [11, 15]]) for (let s = 0; s < 128; s++) {
      const a0 = 2 * Math.PI * s / 128, a1 = 2 * Math.PI * (s + 1) / 128;
      pts.push(rr * Math.cos(a0), yy, -rr * Math.sin(a0), rr * Math.cos(a1), yy, -rr * Math.sin(a1));
    }
    const lg = new THREE.BufferGeometry(); lg.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    lidParts.add(new THREE.LineSegments(lg, lm));
  }
  turned(lidParts, ring(135, 169, 15, 29), 'pvdf', 9, {}, 128);
  const rodAt = [];
  for (let k = 0; k < 3; k++) {
    const a = (90 + 120 * k) * Math.PI / 180, x = 150 * Math.cos(a), z = -150 * Math.sin(a);
    rodAt.push([x, z]);
    add(lidParts, latheSharp(ring(0, 8, 29, 160), 24), MAT.steel, 9, { at: [x, 0, z] });
  }
  turned(lidParts, ring(120, 180, 160, 172), 'pvdf', 9, {}, 128);
  turned(lidG, ring(8, 10, 3, 260), 'pfa', 11, {}, 32);
  turned(lidG, ring(2.2, 3.2, 2, 275), 'pfa', 11, {}, 24);
  {
    const tee = new THREE.CylinderGeometry(6, 6, 50, 24); tee.rotateZ(Math.PI / 2);
    add(lidG, tee, MAT.pfa, 11, { at: [35, 200, 0] });
  }
  const uvCaps = new THREE.Group(); lidParts.add(uvCaps); uvCaps.visible = false;
  const uvMeshes = [turned(lidParts, ring(99, 145, 31, 61), 'uv', 12, { capInto: uvCaps }, 96)];
  uvMeshes.forEach((m) => { m.visible = false; });
  // 10 lift cylinders (fixed) with rods that follow the lift plate
  const pistonRods = [];
  for (const [x, z] of rodAt) {
    add(cylG, latheSharp(ring(0, 18, 240, 295), 32), MAT.steel, 10, { at: [x, 0, z] });
    pistonRods.push(add(cylG, latheSharp(ring(0, 6, 0, 1), 16), MAT.steel, 10, { at: [x, 172, z] }));
  }

  // ------------------------------------------------------------------ tracers
  const NW = 650, NG = 320;
  function makePoints(n, size) {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(n * 3).fill(0), col = new Float32Array(n * 3).fill(1);
    for (let i = 0; i < n; i++) pos[3 * i + 1] = -9999;
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    const m = new THREE.PointsMaterial({ size, sizeAttenuation: false, vertexColors: true, transparent: true, opacity: 0.95, depthWrite: false });
    clipMats.push(m); m.clippingPlanes = [cutPlane];
    const p = new THREE.Points(g, m); p.frustumCulled = false; p.renderOrder = 4; scene.add(p);
    return { p, pos, col, n, st: new Int8Array(n), r: new Float32Array(n), a: new Float32Array(n), x: new Float32Array(n), y: new Float32Array(n),
      z: new Float32Array(n), vx: new Float32Array(n), vy: new Float32Array(n), vz: new Float32Array(n), fy: new Float32Array(n),
      t: new Float32Array(n), r0: new Float32Array(n), y0: new Float32Array(n), acc: 0, cursor: 0 };
  }
  const water = makePoints(NW, 3.6), gas = makePoints(NG, 3.4);
  function spawn(T) {
    for (let k = 0; k < T.n; k++) { const i = (T.cursor + k) % T.n; if (T.st[i] === 0) { T.cursor = (i + 1) % T.n; return i; } }
    return -1;
  }
  const wrap = (a) => { while (a > Math.PI) a -= 2 * Math.PI; while (a < -Math.PI) a += 2 * Math.PI; return a; };
  function setCol(T, i, c) { T.col[3 * i] = c.r; T.col[3 * i + 1] = c.g; T.col[3 * i + 2] = c.b; }

  // ------------------------------------------------------------------ colours from the theme
  const COL = {};
  function readTheme() {
    COL.stage = new THREE.Color(css('--stage') || '#dde5e8');
    COL.water = new THREE.Color(css('--water') || '#2c84c6');
    COL.gas = new THREE.Color(css('--gas') || '#8558cf');
    COL.clean = new THREE.Color('#a9d6f0');
    COL.inert = new THREE.Color('#a9b4bb');
    scene.background = COL.stage;
    drawCharts(true);
  }

  // ------------------------------------------------------------------ simulation (worker, with a main-thread fallback)
  const coreSrc = document.getElementById('core').textContent;
  let worker = null, jobId = 0;
  try {
    const blob = new Blob([coreSrc + '\nself.onmessage = function (e) { self.postMessage({ id: e.data.id, r: compute(e.data.set) }); };'], { type: 'text/javascript' });
    worker = new Worker(URL.createObjectURL(blob));
    worker.onmessage = (e) => { if (e.data.id === jobId) onResult(e.data.r); };
    worker.onerror = () => { worker = null; requestSim(); };
  } catch (e) { worker = null; }
  function requestSim() {
    jobId++;
    $('#busy').hidden = false;
    const id = jobId, set = Object.assign({}, settings);
    if (worker) worker.postMessage({ id, set });
    else setTimeout(() => { if (id === jobId) onResult(compute(set)); }, 30);
  }
  let restartAtStrip = false;
  function niceFine(v) {
    if (!(v > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v))), m = v / p;
    for (const k of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m <= k + 1e-9) return k * p;
    return 10 * p;
  }
  function rateScale(r) {
    // one scale for the whole strip; the spike just behind the clearing front is cut off
    const rmm = r.rv.map((x) => x * 1000);
    let m = 0;
    rmm.forEach((x, k) => { if (x >= 20) m = Math.max(m, r.rate0[k]); });
    for (const s of r.snaps) {
      const front = s.delta.findIndex((d) => d > 0);
      if (front < 0) continue;
      const from = Math.max(rmm[front] + 6, 20);
      rmm.forEach((x, k) => { if (x >= from && s.delta[k] > 0) m = Math.max(m, s.rate[k]); });
    }
    return niceFine(m * 6e10 * 1.1);
  }
  function onResult(r) {
    sim = r;
    sim.yRate = rateScale(r);
    $('#busy').hidden = true;
    buildSteps();
    const strip = steps[3];
    if (firstResult) { procT = strip.t0 + 0.4 * strip.dur; firstResult = false; }
    else if (restartAtStrip) { procT = strip.t0; restartAtStrip = false; }
    else procT = Math.min(procT, total - 0.01);
    setFilmHeights();
    renderStatic();
    drawCharts(true);
  }

  // ------------------------------------------------------------------ cycle steps
  const timelineEl = $('#timeline');
  function buildSteps() {
    const open = settings.open;
    const tStrip = sim && isFinite(sim.tClear) ? sim.tClear * 1.1 : 180;
    steps = [
      { id: 'load', name: 'Load', long: 'Load the wafer', dur: 10 },
      { id: 'close', name: open ? 'Ready' : 'Close', long: open ? 'Ready, no lid' : 'Close the lid', dur: 4 },
      { id: 'prime', name: 'Purge', long: open ? 'Spin up' : 'Purge the gap, spin up', dur: 6 },
      { id: 'strip', name: 'Strip', long: 'Strip the resist', dur: tStrip },
      { id: 'rinse', name: 'Rinse', long: 'Rinse', dur: 30 },
      { id: 'dry', name: 'Dry', long: 'Spin dry', dur: 20 },
      { id: 'open', name: open ? 'Stop' : 'Open', long: open ? 'Spin down' : 'Open the lid', dur: 6 },
      { id: 'unload', name: 'Unload', long: 'Unload the wafer', dur: 10 },
    ];
    let t = 0;
    for (const s of steps) { s.t0 = t; t += s.dur; }
    total = t;
    timelineEl.innerHTML = '';
    steps.forEach((s, i) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'seg'; b.style.flexGrow = String(Math.max(s.dur, 14));
      b.setAttribute('aria-label', s.long + ', ' + fmtClock(s.dur)); b.title = s.long + ', ' + fmtClock(s.dur);
      b.innerHTML = '<span class="fill"></span><span class="lbl"></span>';
      b.querySelector('.lbl').textContent = s.name;
      b.addEventListener('click', () => { procT = s.t0 + 0.001; });
      timelineEl.appendChild(b);
      s.el = b;
    });
    fitLabels();
  }
  function fitLabels() {
    for (const s of steps) {
      if (!s.el) continue;
      s.el.classList.remove('tight');
      const l = s.el.querySelector('.lbl');
      if (l.offsetWidth > s.el.clientWidth - 6) s.el.classList.add('tight');
    }
  }
  function stateAt(T) {
    let i = steps.findIndex((s) => T < s.t0 + s.dur);
    if (i < 0) i = steps.length - 1;
    const s = steps[i], tau = clamp(T - s.t0, 0, s.dur), f = s.dur > 0 ? tau / s.dur : 1;
    const open = settings.open, rpmSet = settings.rpm;
    const coverGas = settings.cover === 'nitrogen' ? 'inert' : (settings.cover === 'air' ? 'off' : 'ozone');
    const st = { i, s, tau, f, lift: 60, rpm: 0, water: 'off', gas: 'off', wx: 0, wy: 0, strip: -1, film: 0, text: '' };
    switch (s.id) {
      case 'load':
        if (f < 0.6) { st.wx = lerp(-470, 0, ease(f / 0.6)); st.wy = 30; } else { st.wy = lerp(30, 0, ease((f - 0.6) / 0.4)); }
        st.text = 'The robot hands the wafer in through the side slot and the lift pins set it on the chuck.';
        break;
      case 'close':
        st.lift = open ? 60 : 60 * (1 - ease(f));
        st.text = open ? 'Open process: no lid, room air over the wafer, 100 m³/h of exhaust.' : 'Three cylinders lower the quartz lid to 3 mm above the wafer.';
        break;
      case 'prime':
        st.lift = open ? 60 : 0; st.rpm = rpmSet * Math.min(tau / 4, 1);
        st.gas = open ? 'off' : (tau < 3 ? 'inert' : coverGas);
        st.text = open ? 'Spin up. Ozone water runs to the drain until the monitor reads steady.' : 'Oxygen purges the gap, then the off-gas takes over. Ozone water runs to the drain until the monitor reads steady.';
        break;
      case 'strip':
        st.lift = open ? 60 : 0; st.rpm = rpmSet; st.water = 'ozone'; st.gas = open ? 'off' : coverGas; st.strip = tau; st.film = 1;
        st.text = sim && isFinite(sim.tClear) && tau > sim.tClear ? 'End point: the drain ozone has risen to the bare-wafer value. Short over-strip.'
          : (open ? 'Ozone water spreads as a film; room air takes ozone from its surface.' : 'Ozone water spreads as a film; the off-gas over it keeps the film from losing ozone. The resist clears from the centre outward.');
        break;
      case 'rinse':
        st.lift = open ? 60 : 0; st.rpm = rpmSet; st.water = 'clean'; st.gas = open ? 'off' : 'inert'; st.strip = Infinity; st.film = 1;
        st.text = 'Ozone-free water rinses the wafer; oxygen sweeps the gap back to the loop.';
        break;
      case 'dry':
        st.lift = open ? 60 : 0; st.rpm = lerp(rpmSet, 2500, Math.min(tau / 3, 1)); st.gas = open ? 'off' : 'inert'; st.strip = Infinity; st.film = Math.max(0, 1 - tau / 3);
        st.text = 'Spin dry at 2500 rpm with nitrogen in the gap.';
        break;
      case 'open':
        st.rpm = 2500 * Math.max(0, 1 - tau / 2.5); st.strip = Infinity;
        st.lift = open ? 60 : (tau < 3 ? 0 : 60 * ease((tau - 3) / 3)); st.gas = open || tau >= 3 ? 'off' : 'inert';
        st.text = open ? 'Spin down.' : 'Spin down. The gap is purged before the lid lifts 60 mm.';
        break;
      case 'unload':
        st.strip = Infinity;
        if (f < 0.4) st.wy = lerp(0, 30, ease(f / 0.4)); else { st.wy = 30; st.wx = lerp(0, -470, ease((f - 0.4) / 0.6)); }
        st.text = 'The wafer leaves through the slot.';
        break;
    }
    return st;
  }

  // strip state from the simulation snapshots
  const NR = K + 1;
  const zeros = new Float32Array(NR);
  function stripAt(t) {
    if (!sim || !sim.snaps.length) return null;
    const S = sim.snaps, d0 = settings.resist_um * 1e-6;
    if (t < 0) return { delta: new Float32Array(NR).fill(d0), rate: sim.rate0, cm: sim.cm0, drain: sim.summary.drainFull, carbon: 0, cleared: 0, front: 0 };
    if (t >= sim.tClear) return { delta: zeros, rate: zeros, cm: S[S.length - 1].cm, drain: sim.summary.drainBare, carbon: 0, cleared: 1, front: 150 };
    let lo = 0, hi = S.length - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (S[mid].t <= t) lo = mid; else hi = mid; }
    const s = S[lo], n = S[Math.min(lo + 1, S.length - 1)], dt = t - s.t, w = n.t > s.t ? clamp(dt / (n.t - s.t), 0, 1) : 0;
    const delta = new Float32Array(NR), rate = new Float32Array(NR);
    let area = 0, cl = 0, front = 0, frontOpen = true;
    for (let k = 0; k < NR; k++) {
      delta[k] = Math.max(s.delta[k] - s.rate[k] * dt, 0);
      rate[k] = delta[k] > 0 ? s.rate[k] : 0;
      const r = sim.rv[k] * 1000, a = Math.PI * ((r + 0.8333) ** 2 - Math.max(r - 0.8333, 0) ** 2);
      area += a; if (delta[k] <= 0) cl += a;
      if (frontOpen && delta[k] <= 0) front = r; else frontOpen = false;
    }
    return { delta, rate, cm: s.cm, drain: lerp(s.drain, n.drain, w), carbon: lerp(s.carbon, n.carbon, w), cleared: cl / area, front };
  }

  // ------------------------------------------------------------------ surfaces
  let filmY = new Float32Array(NR);
  function setFilmHeights() {
    if (!sim) return;
    for (let k = 0; k < NR; k++) filmY[k] = 0.12 + Math.min(sim.hv[k] * 1000 * 50, 2.3);
  }
  const filmAt = (rmm) => { const x = clamp(rmm / 150 * K, 0, K), k = Math.floor(x), f = x - k; return k >= K ? filmY[K] : lerp(filmY[k], filmY[k + 1], f); };
  const RES = new THREE.Color('#e8862a'), PALE = new THREE.Color('#cfe7f7'), DEEP = new THREE.Color('#0f4ea6'), CLEANF = new THREE.Color('#e3f2fb');
  const tmpC = new THREE.Color();
  function paintWafer(delta, d0) {
    const col = waferTopGeo.attributes.color.array;
    for (let k = 0; k <= K; k++) {
      const f = delta ? clamp(delta[k] / d0, 0, 1) : 1;
      const tint = f > 0 ? 0.5 + 0.5 * f : 0;
      tmpC.setRGB(1, 1, 1).lerp(RES, tint);
      for (let s = 0; s <= MS; s++) { const i = 3 * (k * (MS + 1) + s); col[i] = tmpC.r; col[i + 1] = tmpC.g; col[i + 2] = tmpC.b; }
    }
    waferTopGeo.attributes.color.needsUpdate = true;
    for (let k = 0; k <= K; k++) resistTop[k] = delta ? 0.6 * clamp(delta[k] / d0, 0, 1) : 0.6;
    setStrip(resistSec, () => 0, (k) => resistTop[k]);
  }
  function paintFilm(cm, amount, clean) {
    const pos = filmGeo.attributes.position.array, col = filmGeo.attributes.color.array;
    const cRef = Math.max(sim ? sim.summary.cNoz : 100, 1);
    for (let k = 0; k <= K; k++) {
      const y = 0.06 + (filmY[k] - 0.06) * amount;
      if (clean || !cm) tmpC.copy(CLEANF); else tmpC.copy(PALE).lerp(DEEP, clamp(cm[k] * 47.998 / cRef, 0, 1));
      for (let s = 0; s <= MS; s++) { const i = 3 * (k * (MS + 1) + s); pos[i + 1] = y; col[i] = tmpC.r; col[i + 1] = tmpC.g; col[i + 2] = tmpC.b; }
    }
    filmGeo.attributes.position.needsUpdate = true; filmGeo.attributes.color.needsUpdate = true;
    filmMesh.material.opacity = 0.46 * Math.min(amount * 1.5, 1);
    filmMesh.visible = amount > 0.01;
    filmSec.visible = amount > 0.01;
    const cols = [];
    for (let k = 0; k <= K; k++) { if (clean || !cm) cols.push(CLEANF.clone()); else cols.push(PALE.clone().lerp(DEEP, clamp(cm[k] * 47.998 / cRef, 0, 1))); }
    setStrip(filmSec, (k) => resistTop[k], (k) => Math.max(resistTop[k], 0.06 + (filmY[k] - 0.06) * amount), (k) => cols[k]);
  }

  // ------------------------------------------------------------------ tracer motion
  function stepWater(dt, mode, omega, lift) {
    const T = water;
    if (mode !== 'off') {
      T.acc += dt * 170 * clamp(settings.flow_lpm / 2, 0.4, 1.6);
      const c = mode === 'ozone' ? COL.water : COL.clean;
      while (T.acc >= 1) {
        T.acc -= 1;
        const i = spawn(T); if (i < 0) break;
        T.st[i] = 1; T.r[i] = 2 * Math.sqrt(Math.random()); T.a[i] = Math.random() * 6.2832; T.y[i] = 2 + lift; T.fy[i] = 0.25 + 0.75 * Math.random();
        setCol(T, i, c);
      }
    }
    for (let i = 0; i < T.n; i++) {
      const st = T.st[i];
      if (st === 0) continue;
      if (st === 1) {
        T.y[i] -= 480 * dt; T.x[i] = T.r[i] * Math.cos(T.a[i]); T.z[i] = -T.r[i] * Math.sin(T.a[i]);
        if (T.y[i] <= filmAt(T.r[i])) T.st[i] = 2;
      } else if (st === 2) {
        T.r[i] += 78 * Math.pow(Math.max(T.r[i], 3) / 50, -1 / 3) * dt; T.a[i] += omega * dt;
        T.y[i] = 0.08 + T.fy[i] * (filmAt(T.r[i]) - 0.08);
        T.x[i] = T.r[i] * Math.cos(T.a[i]); T.z[i] = -T.r[i] * Math.sin(T.a[i]);
        if (T.r[i] >= 150) {
          T.st[i] = 3;
          const a = T.a[i], vt = Math.max(omega, 0.6) * 150, vr = 55;
          T.vx[i] = -vt * Math.sin(a) + vr * Math.cos(a); T.vz[i] = -vt * Math.cos(a) - vr * Math.sin(a); T.vy[i] = 0;
        }
      } else if (st === 3) {
        T.x[i] += T.vx[i] * dt; T.z[i] += T.vz[i] * dt; T.vy[i] -= 1600 * dt; T.y[i] = Math.max(T.y[i] + T.vy[i] * dt, -60);
        if (Math.hypot(T.x[i], T.z[i]) >= 199) { T.st[i] = 4; T.a[i] = Math.atan2(-T.z[i], T.x[i]); T.r[i] = 199; }
      } else if (st === 4) {
        T.y[i] -= 170 * dt; T.x[i] = T.r[i] * Math.cos(T.a[i]); T.z[i] = -T.r[i] * Math.sin(T.a[i]);
        if (T.y[i] <= -86) { T.st[i] = 5; T.y[i] = -86; }
      } else if (st === 5) {
        const target = Math.sin(T.a[i]) >= 0 ? Math.PI / 2 : -Math.PI / 2, d = wrap(target - T.a[i]);
        T.a[i] += Math.sign(d) * Math.min(Math.abs(d), 1.5 * dt);
        T.r[i] += (190 - T.r[i]) * Math.min(4 * dt, 1);
        T.x[i] = T.r[i] * Math.cos(T.a[i]); T.z[i] = -T.r[i] * Math.sin(T.a[i]);
        if (Math.abs(d) < 0.04) T.st[i] = 6;
      } else if (st === 6) {
        T.y[i] -= 230 * dt;
        if (T.y[i] < -180) { T.st[i] = 0; T.y[i] = -9999; }
      }
    }
    flush(T);
  }
  function stepGas(dt, mode, omega, lift) {
    const T = gas;
    if (mode !== 'off') {
      T.acc += dt * 80 * clamp(Math.sqrt(settings.gas_Nlpm), 0.5, 1.6);
      const c = mode === 'ozone' ? COL.gas : COL.inert;
      while (T.acc >= 1) {
        T.acc -= 1;
        const i = spawn(T); if (i < 0) break;
        T.st[i] = 1; T.r[i] = 4.2 + 3.4 * Math.random(); T.a[i] = Math.random() * 6.2832; T.y[i] = 46 + lift + 20 * Math.random(); T.fy[i] = 0.15 + 0.8 * Math.random();
        setCol(T, i, c);
      }
    }
    for (let i = 0; i < T.n; i++) {
      const st = T.st[i];
      if (st === 0) continue;
      if (st === 1) {
        T.y[i] -= 150 * dt;
        if (T.y[i] <= 2.6 + lift) { T.st[i] = 2; T.r[i] = 10; }
        T.x[i] = T.r[i] * Math.cos(T.a[i]); T.z[i] = -T.r[i] * Math.sin(T.a[i]);
      } else if (st === 2) {
        T.r[i] += 42 * Math.sqrt(60 / Math.max(T.r[i], 10)) * dt; T.a[i] += 0.55 * omega * dt;
        const fy = filmAt(Math.min(T.r[i], 150));
        T.y[i] = fy + T.fy[i] * (2.85 + lift - fy);
        T.x[i] = T.r[i] * Math.cos(T.a[i]); T.z[i] = -T.r[i] * Math.sin(T.a[i]);
        if (T.r[i] >= 151) { T.st[i] = 3; T.t[i] = 0; T.r0[i] = T.r[i]; T.y0[i] = T.y[i]; }
      } else if (st === 3) {
        T.t[i] += dt; const f = Math.min(T.t[i] / 0.6, 1);
        T.r[i] = lerp(T.r0[i], 179, f); T.y[i] = lerp(T.y0[i], 21, ease(f)); T.a[i] += 0.3 * omega * dt;
        T.x[i] = T.r[i] * Math.cos(T.a[i]); T.z[i] = -T.r[i] * Math.sin(T.a[i]);
        if (f >= 1) T.st[i] = 4;
      } else if (st === 4) {
        const target = Math.cos(T.a[i]) >= 0 ? 0 : Math.PI, d = wrap(target - T.a[i]);
        T.a[i] += Math.sign(d) * Math.min(Math.abs(d), 1.1 * dt);
        T.r[i] += (192 - T.r[i]) * Math.min(3 * dt, 1); T.y[i] += (24 - T.y[i]) * Math.min(3 * dt, 1);
        T.x[i] = T.r[i] * Math.cos(T.a[i]); T.z[i] = -T.r[i] * Math.sin(T.a[i]);
        if (Math.abs(d) < 0.05) { T.st[i] = 5; T.x[i] = 195 * Math.sign(Math.cos(T.a[i]) || 1); T.z[i] = 0; }
      } else if (st === 5) {
        T.y[i] += 95 * dt;
        if (T.y[i] > 78) { T.st[i] = 0; T.y[i] = -9999; }
      }
    }
    flush(T);
  }
  function flush(T) {
    for (let i = 0; i < T.n; i++) {
      if (T.st[i] === 0) { T.pos[3 * i + 1] = -9999; continue; }
      T.pos[3 * i] = T.x[i]; T.pos[3 * i + 1] = T.y[i]; T.pos[3 * i + 2] = T.z[i];
    }
    T.p.geometry.attributes.position.needsUpdate = true; T.p.geometry.attributes.color.needsUpdate = true;
  }
  function clearTracers(T) { for (let i = 0; i < T.n; i++) { T.st[i] = 0; } flush(T); }

  // ------------------------------------------------------------------ readouts and charts
  const readEl = $('#readouts'), warnEl = $('#warns');
  function rowsHTML(rows) {
    return rows.map(([k, v, big]) => '<dt>' + k + '</dt><dd' + (big ? ' class="big"' : '') + '>' + v + '</dd>').join('');
  }
  function tilesHTML(rows) {
    return rows.map(([k, v, big]) => '<div class="tile' + (big ? ' big' : '') + '"><span>' + k + '</span><b>' + v + '</b></div>').join('');
  }
  function coverText() {
    if (!sim) return '';
    const s = sim.summary;
    if (settings.cover === 'offgas') return (s.yOff * 100).toFixed(1) + ' % ozone, off-gas';
    if (settings.cover === 'fresh') return (s.y * 100).toFixed(1) + ' % ozone, fresh gas';
    if (settings.cover === 'nitrogen') return 'nitrogen, no ozone';
    return 'room air, open bowl';
  }
  let lastStrip = null, lastState = null;
  function renderLive(st) {
    if (!sim) return;
    const s = sim.summary, sp = lastStrip;
    const rows = [
      ['Spin speed', Math.round(st.rpm) + ' rpm'],
      ['Ozone at the nozzle', s.cNoz.toFixed(0) + ' mg/L (' + s.S.toFixed(2) + '× saturated)'],
      ['Gas over the film', st.gas === 'off' ? (settings.open ? 'room air, open bowl' : 'none') : (st.gas === 'inert' ? 'oxygen or nitrogen purge' : coverText())],
      ['Film at the edge', (s.hEdge * 1e6).toFixed(0) + ' µm, renewed every ' + (s.residence * 1000).toFixed(0) + ' ms'],
    ];
    if (sp && st.strip >= 0) {
      const rem = sp.rate, d = sp.delta;
      let num = 0, den = 0;
      for (let k = 0; k < NR; k++) if (d[k] > 0 && sim.rv[k] >= 0.01) { const r = sim.rv[k]; num += rem[k] * r; den += r; }
      rows.push(['Resist cleared', (sp.cleared * 100).toFixed(0) + ' % of the area' + (sp.front > 0 ? ', to ' + sp.front.toFixed(0) + ' mm' : '')]);
      rows.push(['Strip rate on the resist left', den > 0 ? (num / den * 6e10).toFixed(0) + ' nm/min' : 'none left']);
      rows.push(['Drain ozone', sp.drain.toFixed(1) + ' mg/L', true]);
      rows.push(['Carbon off the wafer', sp.carbon.toFixed(1) + ' mg/min']);
    } else {
      rows.push(['Resist cleared', st.s.id === 'load' || st.s.id === 'close' || st.s.id === 'prime' ? 'not started' : '100 %']);
    }
    rows.push(['Time to clear ' + settings.resist_um.toFixed(1) + ' µm', isFinite(sim.tClear) ? (sim.tClear / 60).toFixed(2) + ' min (' + (s.tStatic / 60).toFixed(2) + ' steady)' : 'does not clear', true]);
    rows.push(['Wafer cycle', Math.floor(total / 60) + ' min ' + Math.round(total % 60) + ' s']);
    readEl.innerHTML = tilesHTML(rows);
  }
  function renderStatic() {
    if (!sim) return;
    const s = sim.summary, w = [];
    if (s.S > 2) w.push('Supersaturation ' + s.S.toFixed(2) + ', above 2: bubbles are likely at the nozzle. Warm the dissolver or weaken the gas.');
    if (s.hEdge < 20e-6) w.push('Edge film ' + (s.hEdge * 1e6).toFixed(0) + ' µm, under 20 µm: it may break into rivulets.');
    if (s.inertiaMid > 0.5) w.push('Film inertia is not small at mid-radius: the film model is less reliable here.');
    if (s.approach < 0.75) w.push('The dissolver reaches only ' + s.approach.toFixed(2) + ' of equilibrium: the water takes ' + (s.dissolved * 100).toFixed(0) + ' % of the generator\'s ozone. More gas flow would help.');
    if (!isFinite(sim.tClear)) w.push('The edge never clears at these settings.');
    let html = w.map((t) => '<div class="warn">' + t + '</div>').join('');
    if (!w.length) html = '<div class="okline">Within the design limits: at most 2 times saturated, edge film at least 20 µm.</div>';
    if (settings.open) html += '<div class="okline">Open process for comparison: no lid, room air over the film.</div>';
    warnEl.innerHTML = html;
    const bal = $('#bal'), rowsB = $('#balrows');
    if (sim.shares) {
      const sh = sim.shares;
      const parts = [
        ['Never dissolved' + (settings.cover === 'offgas' ? ', fed over the film' : ''), sh.notDissolved, '#a9b4bb'],
        ['Left the film for the gas', sh.gas, 'var(--gas)'],
        ['Left with the drain', sh.drain, 'var(--water)'],
        ['Stripped the resist', sh.resist, 'var(--resist)'],
      ];
      bal.innerHTML = parts.map(([, v, c]) => '<div style="flex:' + Math.max(v, 0.002).toFixed(4) + ';background:' + c + '"></div>').join('');
      rowsB.innerHTML = rowsHTML(parts.map(([k, v]) => [k, (v * 100).toFixed(1) + ' %'])
        .concat([['Ozone made per wafer', s.ozonePerWafer.toFixed(2) + ' g'], ['Generator', s.gen_g_min.toFixed(2) + ' g/min, ' + (s.y * 100).toFixed(1) + ' % ozone']]));
    } else { bal.innerHTML = ''; rowsB.innerHTML = ''; }
  }
  function chartCtx(cv) {
    const r = cv.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(Math.round(r.width), 10), h = Math.max(Math.round(r.height), 10);
    if (cv.width !== w * dpr || cv.height !== h * dpr) { cv.width = w * dpr; cv.height = h * dpr; }
    const g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
    return { g, w, h };
  }
  function niceMax(v) { if (!(v > 0)) return 1; const p = Math.pow(10, Math.floor(Math.log10(v))), m = v / p; return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p; }
  function drawChart(cv, o) {
    const { g, w, h } = chartCtx(cv);
    const L = 40, R = 14, Tp = 8, B = 20, pw = w - L - R, ph = h - Tp - B;
    const X = (x) => L + x / o.xMax * pw, Y = (y) => Tp + ph - clamp(y / o.yMax, 0, 1.05) * ph;
    const ink = css('--muted') || '#586973', line = css('--line') || '#ccd6da';
    g.font = '10.5px "IBM Plex Mono", ui-monospace, monospace'; g.fillStyle = ink; g.strokeStyle = line; g.lineWidth = 1;
    for (let k = 0; k <= 2; k++) {
      const yv = o.yMax * k / 2, y = Y(yv);
      g.beginPath(); g.moveTo(L, y + 0.5); g.lineTo(L + pw, y + 0.5); g.stroke();
      g.textAlign = 'right'; g.textBaseline = 'middle'; g.fillText(o.yFmt(yv), L - 5, y);
    }
    g.textAlign = 'center'; g.textBaseline = 'top';
    for (const xv of o.xTicks) g.fillText(o.xFmt(xv), X(xv), Tp + ph + 5);
    for (const v of o.vlines || []) {
      g.save(); g.strokeStyle = v.color; g.setLineDash([3, 3]); g.beginPath(); g.moveTo(X(v.x) + 0.5, Tp); g.lineTo(X(v.x) + 0.5, Tp + ph); g.stroke(); g.restore();
      if (v.label) { g.fillStyle = v.color; g.textAlign = X(v.x) > L + pw - 60 ? 'right' : 'left'; g.textBaseline = 'top'; g.fillText(v.label, X(v.x) + (g.textAlign === 'left' ? 4 : -4), Tp + 1); g.fillStyle = ink; }
    }
    for (const hl of o.hlines || []) {
      g.save(); g.strokeStyle = hl.color; g.setLineDash([4, 3]); g.beginPath(); g.moveTo(L, Y(hl.y) + 0.5); g.lineTo(L + pw, Y(hl.y) + 0.5); g.stroke(); g.restore();
      if (hl.label) { g.fillStyle = hl.color; g.textAlign = 'left'; g.textBaseline = 'bottom'; g.fillText(hl.label, L + 4, Y(hl.y) - 2); g.fillStyle = ink; }
    }
    for (const s of o.series) {
      if (!s.xs.length) continue;
      g.save(); g.beginPath(); g.rect(L, 0, pw + 1, Tp + ph + 1); g.clip();
      g.strokeStyle = s.color; g.lineWidth = s.width || 1.8; if (s.dash) g.setLineDash(s.dash);
      g.beginPath(); s.xs.forEach((x, i) => { const px = X(x), py = Y(s.ys[i]); if (i) g.lineTo(px, py); else g.moveTo(px, py); });
      if (s.fill) { g.lineTo(X(s.xs[s.xs.length - 1]), Y(0)); g.lineTo(X(s.xs[0]), Y(0)); g.closePath(); g.globalAlpha = 0.35; g.fillStyle = s.color; g.fill(); g.globalAlpha = 1; }
      else g.stroke();
      if (s.fill) { g.beginPath(); s.xs.forEach((x, i) => { const px = X(x), py = Y(s.ys[i]); if (i) g.lineTo(px, py); else g.moveTo(px, py); }); g.stroke(); }
      g.restore();
      if (s.label) {
        let k = 0; while (k < s.xs.length - 1 && s.xs[k] < s.labelAt) k++;
        g.fillStyle = s.color; g.textAlign = 'right'; g.textBaseline = 'top'; g.fillText(s.label, X(s.xs[k]), Math.min(Y(s.ys[k]) + 4, Tp + ph - 12)); g.fillStyle = ink;
      }
    }
    if (o.cursor !== undefined && o.cursor !== null) {
      g.save(); g.strokeStyle = css('--ink') || '#13212a'; g.lineWidth = 1.2; g.beginPath(); g.moveTo(X(o.cursor) + 0.5, Tp); g.lineTo(X(o.cursor) + 0.5, Tp + ph); g.stroke(); g.restore();
    }
  }
  let chartClock = 0;
  function drawCharts(force) {
    if (!sim) return;
    const now = performance.now();
    if (!force && now - chartClock < 120) return;
    chartClock = now;
    const rmm = sim.rv.map((r) => r * 1000), d0 = settings.resist_um * 1000;
    const sp = lastStrip, st = lastState;
    const delta = sp ? Array.from(sp.delta, (d) => d * 1e9) : rmm.map(() => d0);
    const resistC = css('--resist') || '#c27626', acc = css('--accent') || '#1f6aa5', waterC = css('--water') || '#2c84c6', muted = css('--muted') || '#586973';
    drawChart($('#chResist'), { xMax: 150, yMax: d0 * 1.1, xTicks: [0, 50, 100, 150], xFmt: (x) => String(x), yFmt: (y) => y.toFixed(0),
      series: [{ xs: rmm, ys: delta, color: resistC, fill: true }], hlines: [{ y: d0, color: muted, label: 'start' }] });
    const keep = rmm.map((r, k) => k).filter((k) => rmm[k] >= 10);
    const xr = keep.map((k) => rmm[k]), r0 = keep.map((k) => sim.rate0[k] * 6e10), rn = keep.map((k) => (sp ? sp.rate[k] : sim.rate0[k]) * 6e10);
    const yR = sim.yRate || niceMax(Math.max(...r0, ...rn) * 1.05);
    drawChart($('#chRate'), { xMax: 150, yMax: yR, xTicks: [0, 50, 100, 150], xFmt: (x) => String(x), yFmt: (y) => y.toFixed(0),
      series: [{ xs: xr, ys: r0, color: muted, dash: [4, 3], width: 1.2, label: 'start', labelAt: 146 }, { xs: xr, ys: rn, color: acc }], vlines: [{ x: 10, color: muted, label: '' }] });
    if (sim.snaps.length) {
      const tEnd = sim.tClear * 1.1, ts = sim.snaps.map((s) => s.t).concat([sim.tClear, tEnd]);
      const ds = sim.snaps.map((s) => s.drain).concat([sim.summary.drainBare, sim.summary.drainBare]);
      const yD = niceMax(sim.summary.drainBare * 1.15);
      const tick = tEnd > 300 ? 120 : tEnd > 120 ? 60 : 30, xt = [];
      for (let t = 0; t <= tEnd; t += tick) xt.push(t);
      drawChart($('#chDrain'), { xMax: tEnd, yMax: yD, xTicks: xt, xFmt: (t) => fmtClock(t), yFmt: (y) => y.toFixed(0),
        series: [{ xs: ts, ys: ds, color: waterC }], hlines: [{ y: sim.summary.drainBare, color: muted, label: 'bare wafer' }],
        vlines: [{ x: sim.tClear, color: acc, label: 'end point' }], cursor: st && st.strip >= 0 ? Math.min(st.strip, tEnd) : null });
    }
    $('#ct1').textContent = 'nm against radius, mm';
  }

  // ------------------------------------------------------------------ settings panel
  const CTL = [
    ['rpm', 'Spin speed', 300, 3000, 100, (v) => v + ' rpm'],
    ['flow_lpm', 'Water flow', 0.5, 3.0, 0.1, (v) => v.toFixed(1) + ' L/min'],
    ['T_C', 'Water at the wafer', 20, 50, 1, (v) => v + ' °C'],
    ['Tc_C', 'Dissolver temperature', 5, 25, 1, (v) => v + ' °C'],
    ['pH', 'pH, set with CO₂', 4.0, 5.6, 0.1, (v) => v.toFixed(1)],
    ['gas_gNm3', 'Generator gas', 100, 400, 10, (v) => v + ' g/Nm³'],
    ['gas_Nlpm', 'Gas flow', 0.5, 3.0, 0.1, (v) => v.toFixed(1) + ' NL/min'],
    ['resist_um', 'Resist thickness', 0.5, 3.0, 0.1, (v) => v.toFixed(1) + ' µm'],
  ];
  const ctlEl = $('#ctls');
  let simTimer = null;
  function scheduleSim() { clearTimeout(simTimer); simTimer = setTimeout(() => { restartAtStrip = true; requestSim(); }, 260); }
  function buildControls() {
    ctlEl.innerHTML = '';
    for (const [key, label, min, max, step, fmt] of CTL) {
      const d = document.createElement('div'); d.className = 'ctl';
      const id = 'c-' + key;
      d.innerHTML = '<label for="' + id + '"></label><output for="' + id + '"></output><input type="range" id="' + id + '">';
      d.querySelector('label').textContent = label;
      const inp = d.querySelector('input'), out = d.querySelector('output');
      inp.min = min; inp.max = max; inp.step = step; inp.value = settings[key];
      out.textContent = fmt(Number(settings[key]));
      inp.addEventListener('input', () => { settings[key] = Number(inp.value); out.textContent = fmt(settings[key]); scheduleSim(); });
      ctlEl.appendChild(d);
    }
    const d = document.createElement('div'); d.className = 'ctl';
    d.innerHTML = '<label for="c-cover">Gas over the film</label><output></output><select id="c-cover"></select>';
    const sel = d.querySelector('select');
    const opts = settings.open ? [['air', 'Room air (open process, no lid)']]
      : [['offgas', 'Off-gas from the dissolver (design)'], ['fresh', 'Fresh generator gas first (idea)'], ['nitrogen', 'Nitrogen, no ozone']];
    sel.innerHTML = opts.map(([v, t]) => '<option value="' + v + '">' + t + '</option>').join('');
    sel.value = settings.cover; sel.disabled = settings.open;
    sel.addEventListener('change', () => { settings.cover = sel.value; scheduleSim(); });
    ctlEl.appendChild(d);
  }
  function preset(p) { settings = Object.assign({}, p); buildControls(); restartAtStrip = true; requestSim(); }
  $('#pDesign').addEventListener('click', () => preset(DESIGN));
  $('#pOpen').addEventListener('click', () => preset(OPEN));

  // parts list
  const partsEl = $('#parts');
  PARTS.forEach(([n, name, mat]) => {
    const li = document.createElement('li');
    li.className = 'part'; li.tabIndex = 0; li.dataset.part = n;
    li.innerHTML = '<span class="n"></span><span class="t"></span>';
    li.querySelector('.n').textContent = n;
    li.querySelector('.t').innerHTML = '';
    const t = li.querySelector('.t'); t.append(name); const sm = document.createElement('small'); sm.textContent = mat; t.append(sm);
    li.addEventListener('mouseenter', () => highlight(n));
    li.addEventListener('mouseleave', () => highlight(0));
    li.addEventListener('focus', () => highlight(n));
    li.addEventListener('blur', () => highlight(0));
    li.addEventListener('click', () => focusPart(n));
    partsEl.appendChild(li);
  });
  let hot = 0;
  function highlight(n) {
    if (hot === n) return;
    for (const k in partMeshes) for (const m of partMeshes[k]) if (m.material.emissive) m.material.emissive.setHex(0x000000);
    hot = n;
    if (n && partMeshes[n]) for (const m of partMeshes[n]) if (m.material.emissive) m.material.emissive.setHex(0x1f6aa5).multiplyScalar(0.55);
    partsEl.querySelectorAll('.part').forEach((li) => li.classList.toggle('hot', Number(li.dataset.part) === n));
  }

  // ------------------------------------------------------------------ views and toggles
  const VIEWS = {
    overview: { p: [-720, 470, 1180], t: [70, -20, 0], fit: true },
    section: { p: [0, 30, 1180], t: [0, -10, 0], fit: true },
    rim: { p: [168, 8, 340], t: [162, -24, 0] },
    top: { p: [0.5, 1250, 1], t: [0, 0, 0], fit: true },
  };
  function viewPos(v) {
    // narrow (portrait) views step back so the whole module stays in the frame
    const t = new THREE.Vector3(...v.t), p = new THREE.Vector3(...v.p);
    if (v.fit) p.sub(t).multiplyScalar(Math.min(Math.max(1.2 / camera.aspect, 1), 1.8)).add(t);
    return { p, t };
  }
  let camAnim = null;
  function goView(name, custom) {
    const v = custom || VIEWS[name], q = viewPos(v);
    camAnim = { t: 0, p0: camera.position.clone(), t0: controls ? controls.target.clone() : new THREE.Vector3(), p1: q.p, t1: q.t };
    document.querySelectorAll('.views button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.view === name)));
  }
  document.querySelectorAll('.views button').forEach((b) => b.addEventListener('click', () => goView(b.dataset.view)));
  function focusPart(n) {
    const a = ANCHOR[n]; if (!a) return;
    const y = a[1] + (LIFTED[n] ? lidG.position.y : 0);
    goView('', { p: [a[0] - 240, y + 160, a[2] + 380], t: [a[0], y, a[2]] });
    highlight(n);
  }
  $('#tCut').addEventListener('change', (e) => { cutOn = e.target.checked; applyCut(); });
  $('#tEncl').addEventListener('change', (e) => { enclG.visible = e.target.checked; });
  $('#tUV').addEventListener('change', (e) => { uvMeshes.forEach((m) => { m.visible = e.target.checked; }); uvCaps.visible = e.target.checked; });
  const tagsEl = $('#tags');
  $('#tTags').addEventListener('change', (e) => { tagsEl.hidden = !e.target.checked; });
  const tagEls = {};
  for (const [n] of PARTS) { const d = document.createElement('div'); d.className = 'tag'; d.textContent = n; tagsEl.appendChild(d); tagEls[n] = d; }

  // transport
  const playBtn = $('#play');
  function setPlaying(p) { playing = p; playBtn.textContent = p ? 'Pause' : 'Play'; playBtn.setAttribute('aria-pressed', String(p)); }
  playBtn.addEventListener('click', () => setPlaying(!playing));
  $('#restart').addEventListener('click', () => { procT = 0; clearTracers(water); clearTracers(gas); setPlaying(true); });
  $('#speed').addEventListener('change', (e) => { speed = Number(e.target.value); });
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) setPlaying(false);

  // hover tooltip
  const tip = $('#tip'), ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
  let pointer = null;
  canvas.addEventListener('pointermove', (e) => { const r = canvas.getBoundingClientRect(); pointer = { x: e.clientX - r.left, y: e.clientY - r.top, w: r.width, h: r.height }; });
  canvas.addEventListener('pointerleave', () => { pointer = null; tip.hidden = true; highlight(0); });
  function hover() {
    if (!pointer || !renderer) return;
    mouse.set(pointer.x / pointer.w * 2 - 1, -(pointer.y / pointer.h) * 2 + 1);
    ray.setFromCamera(mouse, camera);
    const hits = ray.intersectObjects(pickables.filter((m) => m.visible && m.parent.visible && (m.parent.parent ? m.parent.parent.visible : true)), false)
      .filter((h) => !cutOn || h.object.material.clippingPlanes.length === 0 || h.point.z <= 0.5);
    if (!hits.length) { tip.hidden = true; highlight(0); return; }
    const n = hits[0].object.userData.part, p = PARTS[n - 1];
    tip.innerHTML = '<b></b><i></i><span></span>';
    tip.querySelector('b').textContent = n + '  ' + p[1];
    tip.querySelector('i').textContent = p[2];
    tip.querySelector('span').textContent = p[3];
    tip.hidden = false;
    const tx = Math.min(pointer.x + 14, pointer.w - 270), ty = Math.min(pointer.y + 14, pointer.h - 110);
    tip.style.left = Math.max(tx, 8) + 'px'; tip.style.top = Math.max(ty, 8) + 'px';
    highlight(n);
  }

  // ------------------------------------------------------------------ main loop
  function resize() {
    if (!renderer) return;
    const r = viewEl.getBoundingClientRect();
    renderer.setSize(Math.max(r.width, 10), Math.max(r.height, 10), false);
    camera.aspect = Math.max(r.width, 10) / Math.max(r.height, 10); camera.updateProjectionMatrix();
  }
  new ResizeObserver(() => { resize(); fitLabels(); drawCharts(true); }).observe(viewEl);
  const proj = new THREE.Vector3();
  let last = performance.now(), liveClock = 0, angle = 0, lastPainted = -2;
  function frame(now) {
    const dtw = Math.min((now - last) / 1000, 0.05); last = now;
    if (sim && playing) { procT += dtw * speed; if (procT >= total) { procT = 0; clearTracers(water); clearTracers(gas); } }
    if (sim) {
      const st = stateAt(procT);
      lastState = st;
      const omega = st.rpm / 60 * 2 * Math.PI / 30;
      angle += omega * dtw;
      rotor.rotation.y = angle;
      waferG.rotation.y = angle;
      waferG.position.set(st.wx, st.wy, 0); secG.position.set(st.wx, st.wy, 0);
      lidG.position.y = st.lift;
      lidParts.visible = !settings.open; cylG.visible = !settings.open;
      pistonRods.forEach((m) => { const top = 172 + st.lift; m.position.y = top; m.scale.y = Math.max(240 - top, 0.5); });
      if (st.s.id === 'load' || st.s.id === 'close' || st.s.id === 'prime') lastStrip = stripAt(-1);
      else lastStrip = stripAt(st.strip);
      const stripKey = st.strip < 0 ? -1 : (isFinite(st.strip) ? Math.round(st.strip * 4) : 1e9);
      if (stripKey !== lastPainted) { paintWafer(lastStrip ? lastStrip.delta : null, settings.resist_um * 1e-6); lastPainted = stripKey; }
      paintFilm(lastStrip ? lastStrip.cm : null, st.film, st.water === 'clean' || st.s.id === 'dry');
      stepWater(dtw, st.water, omega, st.lift);
      stepGas(dtw, st.gas, omega, st.lift);
      $('#stepName').textContent = st.s.long;
      $('#stepClock').textContent = fmtClock(st.tau) + ' / ' + fmtClock(st.s.dur) + '  ·  cycle ' + fmtClock(procT);
      steps.forEach((s, i) => { s.el.classList.toggle('now', i === st.i); s.el.querySelector('.fill').style.width = (i < st.i ? 100 : i === st.i ? st.f * 100 : 0) + '%'; });
      if (now - liveClock > 140) { liveClock = now; $('#status').textContent = st.text; renderLive(st); }
      drawCharts(false);
    }
    if (camAnim && controls) {
      camAnim.t = Math.min(camAnim.t + dtw / 0.8, 1);
      const f = ease(camAnim.t);
      camera.position.lerpVectors(camAnim.p0, camAnim.p1, f);
      controls.target.lerpVectors(camAnim.t0, camAnim.t1, f);
      if (camAnim.t >= 1) camAnim = null;
    }
    if (controls) controls.update();
    if (!tagsEl.hidden && renderer) {
      const r = viewEl.getBoundingClientRect();
      for (const [n] of PARTS) {
        const a = ANCHOR[n]; proj.set(a[0], a[1] + (LIFTED[n] ? lidG.position.y : 0), a[2]).project(camera);
        const el = tagEls[n], vis = proj.z < 1 && Math.abs(proj.x) < 1.05 && Math.abs(proj.y) < 1.05 && (n !== 12 || (uvMeshes[0].visible && lidParts.visible)) && (n !== 2 || enclG.visible) && (!settings.open || ![8, 9, 10, 12].includes(n));
        el.style.display = vis ? 'block' : 'none';
        el.style.left = ((proj.x + 1) / 2 * r.width) + 'px'; el.style.top = ((1 - proj.y) / 2 * r.height) + 'px';
      }
    }
    hover();
    if (renderer) renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }

  // theme changes
  if (window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', readTheme);
  new MutationObserver(readTheme).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  buildControls();
  readTheme();
  resize();
  { const q = viewPos(VIEWS.overview); camera.position.copy(q.p); if (controls) { controls.target.copy(q.t); controls.update(); } }
  requestSim();
  requestAnimationFrame(frame);
})();
