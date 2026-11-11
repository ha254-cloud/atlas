"use client";

import { useEffect, useRef, useState } from "react";
import {
  AmbientLight,
  BoxGeometry,
  DirectionalLight,
  Group,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PerspectiveCamera,
  Scene,
  TorusGeometry,
  WebGLRenderer,
} from "three";

const stages = [
  {
    title: "Claim received",
    shortLabel: "Receive",
    detail: "The claim enters a traceable recovery record.",
  },
  {
    title: "Denial reviewed",
    shortLabel: "Review",
    detail: "The denial reason is reviewed and assigned.",
  },
  {
    title: "Evidence assembled",
    shortLabel: "Evidence",
    detail: "Supporting evidence is linked to the case record.",
  },
  {
    title: "Appeal approved",
    shortLabel: "Approve",
    detail: "A person reviews and approves the appeal.",
  },
  {
    title: "Payment verified",
    shortLabel: "Verify",
    detail: "Payment is reconciled against the recovery.",
  },
];

type StageStamp = Mesh<TorusGeometry, MeshStandardMaterial>;

type SceneState = {
  camera: PerspectiveCamera;
  ledger: Group;
  stamps: StageStamp[];
  renderer: WebGLRenderer;
  scene: Scene;
};

function disposeScene(scene: Scene) {
  scene.traverse((object) => {
    if (object instanceof Mesh) {
      object.geometry.dispose();
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach((material) => material.dispose());
    }
  });
}

export function RecoveryJourneyScene() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sceneStateRef = useRef<SceneState | null>(null);
  const activeStepRef = useRef(0);
  const [activeStep, setActiveStep] = useState(0);
  const [sceneUnavailable, setSceneUnavailable] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let renderer: WebGLRenderer;
    try {
      renderer = new WebGLRenderer({
        alpha: true,
        antialias: true,
        canvas,
        powerPreference: "low-power",
      });
    } catch {
      setSceneUnavailable(true);
      return;
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setClearColor(0x000000, 0);

    const scene = new Scene();
    const camera = new PerspectiveCamera(36, 1, 0.1, 100);
    camera.position.set(0, 0, 7.4);
    scene.add(new AmbientLight(0xfff8ea, 2.2));

    const keyLight = new DirectionalLight(0xffe6c6, 3.4);
    keyLight.position.set(-3.5, 4, 5);
    scene.add(keyLight);
    const fillLight = new DirectionalLight(0xd5eee6, 1.8);
    fillLight.position.set(4, -2, 4);
    scene.add(fillLight);

    const ledger = new Group();
    ledger.rotation.set(-0.13, 0.12, -0.025);
    scene.add(ledger);

    const shadow = new Mesh(
      new BoxGeometry(3.55, 2.35, 0.025),
      new MeshBasicMaterial({
        color: 0x173d38,
        opacity: 0.12,
        transparent: true,
        depthWrite: false,
      }),
    );
    shadow.position.set(0, -0.035, -0.35);
    shadow.scale.set(1.04, 1.03, 1);
    ledger.add(shadow);

    const coverMaterial = new MeshStandardMaterial({
      color: 0x145d55,
      metalness: 0.08,
      roughness: 0.68,
    });
    const cover = new Mesh(new BoxGeometry(3.36, 2.28, 0.16), coverMaterial);
    cover.position.z = -0.2;
    ledger.add(cover);

    const spine = new Mesh(
      new BoxGeometry(0.2, 2.31, 0.21),
      new MeshStandardMaterial({ color: 0x104841, metalness: 0.12, roughness: 0.54 }),
    );
    spine.position.z = -0.08;
    ledger.add(spine);

    for (let layer = 0; layer < 7; layer += 1) {
      const z = -0.105 + layer * 0.018;
      const pageColor = layer % 2 === 0 ? 0xe8dfce : 0xf2eadb;
      for (const x of [-0.79, 0.79]) {
        const page = new Mesh(
          new BoxGeometry(1.55, 2.13, 0.018),
          new MeshStandardMaterial({ color: pageColor, roughness: 0.92 }),
        );
        page.position.set(x, 0, z);
        ledger.add(page);
      }
    }

    const leftPage = new Mesh(
      new BoxGeometry(1.55, 2.13, 0.045),
      new MeshStandardMaterial({ color: 0xf8f1e4, roughness: 0.94 }),
    );
    leftPage.position.set(-0.79, 0, 0.005);
    ledger.add(leftPage);
    const rightPage = new Mesh(
      new BoxGeometry(1.55, 2.13, 0.045),
      new MeshStandardMaterial({ color: 0xfaf4e9, roughness: 0.94 }),
    );
    rightPage.position.set(0.79, 0, 0.005);
    ledger.add(rightPage);

    const addRule = (x: number, y: number, width: number, color: number, z = 0.035) => {
      const rule = new Mesh(
        new BoxGeometry(width, 0.018, 0.008),
        new MeshBasicMaterial({ color }),
      );
      rule.position.set(x, y, z);
      ledger.add(rule);
    };

    addRule(-0.79, 0.79, 0.68, 0x145d55, 0.04);
    addRule(-0.79, 0.65, 0.9, 0xb6a98f, 0.04);
    addRule(-0.9, 0.34, 0.78, 0xcfc3ae);
    addRule(-0.83, 0.08, 0.9, 0xcfc3ae);
    addRule(-0.9, -0.18, 0.76, 0xcfc3ae);
    addRule(-0.81, -0.44, 0.92, 0xcfc3ae);
    addRule(-0.89, -0.7, 0.78, 0xcfc3ae);
    addRule(0.79, 0.79, 0.9, 0x145d55, 0.04);
    addRule(0.79, 0.65, 0.68, 0xb6a98f, 0.04);

    const stamps = stages.map((_, index) => {
      const y = 0.38 - index * 0.31;
      addRule(0.65, y, 0.78, 0xcfc3ae);
      const stamp = new Mesh(
        new TorusGeometry(0.074, 0.012, 6, 24),
        new MeshStandardMaterial({
          color: 0xc6b89f,
          emissive: 0x2b1610,
          emissiveIntensity: 0.08,
          metalness: 0.46,
          roughness: 0.4,
        }),
      );
      stamp.position.set(1.36, y, 0.055);
      ledger.add(stamp);
      return stamp;
    });

    const seal = new Mesh(
      new TorusGeometry(0.14, 0.018, 8, 32),
      new MeshStandardMaterial({
        color: 0xb74a35,
        metalness: 0.28,
        roughness: 0.42,
      }),
    );
    seal.position.set(-1.28, -0.83, 0.045);
    ledger.add(seal);

    const bookmark = new Mesh(
      new BoxGeometry(0.12, 0.47, 0.018),
      new MeshStandardMaterial({ color: 0xb74a35, roughness: 0.56 }),
    );
    bookmark.position.set(0.06, -1.02, -0.035);
    ledger.add(bookmark);

    const state = { camera, ledger, stamps, renderer, scene };
    sceneStateRef.current = state;

    const resize = () => {
      const bounds = canvas.parentElement?.getBoundingClientRect();
      if (!bounds?.width || !bounds.height) return;
      renderer.setSize(bounds.width, bounds.height, false);
      camera.aspect = bounds.width / bounds.height;
      camera.updateProjectionMatrix();
      renderer.render(scene, camera);
    };

    const resizeObserver = new ResizeObserver(resize);
    if (canvas.parentElement) resizeObserver.observe(canvas.parentElement);
    resize();

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frameId = 0;
    const clockStart = performance.now();
    const renderFrame = () => {
      if (!reducedMotion) {
        const elapsed = (performance.now() - clockStart) / 1000;
        ledger.rotation.y = 0.12 + Math.sin(elapsed * 0.45) * 0.28;
        ledger.rotation.x = -0.13 + Math.sin(elapsed * 0.32) * 0.045;
        ledger.rotation.z = -0.025 + Math.sin(elapsed * 0.28) * 0.025;
        ledger.position.y = Math.sin(elapsed * 0.58) * 0.035;
      }
      renderer.render(scene, camera);
      if (!reducedMotion) frameId = window.requestAnimationFrame(renderFrame);
    };
    renderFrame();

    return () => {
      window.cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      sceneStateRef.current = null;
      disposeScene(scene);
      renderer.dispose();
    };
  }, []);

  useEffect(() => {
    activeStepRef.current = activeStep;
    const state = sceneStateRef.current;
    if (!state) return;

    state.stamps.forEach((stamp, index) => {
      const selected = index === activeStep;
      stamp.material.color.set(selected ? 0xb74a35 : 0xc6b89f);
      stamp.material.emissive.set(selected ? 0x6a2e24 : 0x2b1610);
      stamp.material.emissiveIntensity = selected ? 0.34 : 0.08;
      stamp.scale.setScalar(selected ? 1.2 : 1);
    });
    state.renderer.render(state.scene, state.camera);
  }, [activeStep]);

  return (
    <figure aria-label="Interactive 3D recovery ledger" className="w-full">
      <div className="flex flex-col items-start gap-1 text-[11px] font-bold uppercase tracking-[0.08em] text-[#48635d] sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:text-xs">
        <span>Recovery sequence</span>
        <span className="text-[#a63f2e]">Illustrative record · no patient data</span>
      </div>

      <div className="relative mx-auto mt-2 aspect-square w-full max-w-[500px]">
        <canvas ref={canvasRef} aria-hidden="true" className="absolute inset-0 h-full w-full" />
        {sceneUnavailable && (
          <div className="absolute inset-0 grid place-items-center text-center">
            <p className="max-w-[15rem] border-y border-[#145d55]/25 py-4 font-editorial text-xl font-bold text-[#145d55]">
              A reviewable recovery ledger, from denial through payment.
            </p>
          </div>
        )}
        <p className="pointer-events-none absolute bottom-4 left-2 text-[11px] font-bold uppercase tracking-[0.08em] text-[#405b55]">
          Human governed · Evidence preserved
        </p>
        <p className="pointer-events-none absolute right-2 top-4 font-editorial text-base font-bold text-[#a63f2e]">
          AR-2026-0041
        </p>
      </div>

      <figcaption className="border-t border-[#145d55]/20 pt-4">
        <ol aria-label="Recovery journey stages" className="grid grid-cols-5 gap-1">
          {stages.map((stage, index) => (
            <li key={stage.title} className="min-w-0">
              <button
                type="button"
                aria-label={`${String(index + 1).padStart(2, "0")}: ${stage.title}`}
                aria-pressed={activeStep === index}
                onClick={() => setActiveStep(index)}
                className={`min-h-14 w-full border-t px-1 pt-2 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#8b3f35] ${
                  activeStep === index
                    ? "border-[#8b3f35] text-[#173f33]"
                    : "border-[#173f33]/25 text-[#68746e] hover:border-[#8b3f35]"
                }`}
              >
                <span className="block text-[10px] font-bold uppercase tracking-[0.06em]">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="mt-1 block text-[11px] font-semibold leading-4">
                  {stage.shortLabel}
                </span>
              </button>
            </li>
          ))}
        </ol>
        <p role="status" className="mt-3 min-h-5 text-sm leading-6 text-[#405b55]">
          <span className="font-semibold text-[#145d55]">{stages[activeStep].title}.</span>{" "}
          {stages[activeStep].detail}
        </p>
      </figcaption>
    </figure>
  );
}