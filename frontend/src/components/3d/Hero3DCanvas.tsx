import React, { useEffect, useRef, useState } from 'react';
import { FileText, Database, ShieldCheck, Cpu, Sparkles } from 'lucide-react';

interface OrbitingCard {
  id: string;
  name: string;
  tag: string;
  icon: typeof FileText;
  angle: number;
  distance: number;
  heightOffset: number;
  speed: number;
  accent: string;
}

export const Hero3DCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0, targetX: 0, targetY: 0 });
  const [activeCard, setActiveCard] = useState<string | null>(null);

  // Orbiting cards configuration
  const [cards, setCards] = useState<OrbitingCard[]>([
    {
      id: 'doc1',
      name: 'Employee_Database_100.pdf',
      tag: '100 Validated Records',
      icon: Database,
      angle: 0,
      distance: 220,
      heightOffset: -40,
      speed: 0.008,
      accent: 'from-cyan-500 to-blue-600',
    },
    {
      id: 'doc2',
      name: 'Q3_Financial_Audit.pdf',
      tag: 'Dense Vector & BM25',
      icon: FileText,
      angle: (2 * Math.PI) / 3,
      distance: 240,
      heightOffset: 30,
      speed: 0.007,
      accent: 'from-indigo-500 to-purple-600',
    },
    {
      id: 'doc3',
      name: 'Neural_RAG_Architecture.pdf',
      tag: 'Cross-Encoder Reranked',
      icon: Cpu,
      angle: (4 * Math.PI) / 3,
      distance: 210,
      heightOffset: -10,
      speed: 0.009,
      accent: 'from-violet-500 to-cyan-500',
    },
  ]);

  // Handle mouse parallax
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const nx = (e.clientX - rect.left) / rect.width - 0.5;
    const ny = (e.clientY - rect.top) / rect.height - 0.5;
    setMousePos((prev) => ({ ...prev, targetX: nx * 35, targetY: ny * 35 }));
  };

  const handleMouseLeave = () => {
    setMousePos((prev) => ({ ...prev, targetX: 0, targetY: 0 }));
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 800);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 550);

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener('resize', handleResize);

    // 3D Particles representing information flow
    interface Particle3D {
      x: number;
      y: number;
      z: number;
      radius: number;
      speed: number;
      angle: number;
      color: string;
      alpha: number;
    }

    const particleCount = 110;
    const particles: Particle3D[] = [];
    const colors = ['#06b6d4', '#3b82f6', '#8b5cf6', '#38bdf8', '#a855f7'];

    for (let i = 0; i < particleCount; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);
      const dist = 70 + Math.random() * 240;
      particles.push({
        x: dist * Math.sin(phi) * Math.cos(theta),
        y: dist * Math.sin(phi) * Math.sin(theta) * 0.45,
        z: dist * Math.cos(phi),
        radius: 1 + Math.random() * 2.2,
        speed: 0.003 + Math.random() * 0.008,
        angle: theta,
        color: colors[Math.floor(Math.random() * colors.length)],
        alpha: 0.3 + Math.random() * 0.7,
      });
    }

    let globalRotation = 0;
    let pulseScale = 1;
    let pulseDirection = 1;

    // Animation Loop
    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Smooth mouse interpolation
      setMousePos((prev) => {
        const dx = prev.targetX - prev.x;
        const dy = prev.targetY - prev.y;
        return {
          ...prev,
          x: prev.x + dx * 0.06,
          y: prev.y + dy * 0.06,
        };
      });

      const centerX = width / 2 + mousePos.x;
      const centerY = height / 2 + mousePos.y;

      globalRotation += 0.004;

      // Pulse calculation for central AI Core
      pulseScale += 0.003 * pulseDirection;
      if (pulseScale > 1.15) pulseDirection = -1;
      if (pulseScale < 0.95) pulseDirection = 1;

      // Draw background ambient glow
      const radialGlow = ctx.createRadialGradient(
        centerX,
        centerY,
        15,
        centerX,
        centerY,
        280
      );
      radialGlow.addColorStop(0, 'rgba(6, 182, 212, 0.28)');
      radialGlow.addColorStop(0.35, 'rgba(59, 130, 246, 0.16)');
      radialGlow.addColorStop(0.7, 'rgba(139, 92, 246, 0.06)');
      radialGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = radialGlow;
      ctx.fillRect(0, 0, width, height);

      // 3D Orbital Rings (Layered perspective ellipses)
      ctx.save();
      ctx.translate(centerX, centerY);
      for (let r = 140; r <= 260; r += 60) {
        ctx.beginPath();
        ctx.ellipse(0, 0, r, r * 0.32, -0.15, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(59, 130, 246, ${0.12 - (r - 140) * 0.0004})`;
        ctx.lineWidth = 1.2;
        ctx.setLineDash([4, 8]);
        ctx.stroke();
      }
      ctx.restore();

      // Render 3D Particles
      particles.forEach((p) => {
        p.angle += p.speed;
        const currentDist = Math.sqrt(p.x * p.x + p.z * p.z);
        const rotX = Math.cos(globalRotation + p.angle) * currentDist;
        const rotZ = Math.sin(globalRotation + p.angle) * currentDist;

        // 3D Perspective Projection
        const fov = 350;
        const perspective = fov / (fov + rotZ);
        const projX = centerX + rotX * perspective;
        const projY = centerY + p.y * perspective * 0.8;
        const projRadius = Math.max(0.6, p.radius * perspective);

        if (perspective > 0) {
          ctx.beginPath();
          ctx.arc(projX, projY, projRadius, 0, Math.PI * 2);
          ctx.fillStyle = p.color;
          ctx.globalAlpha = p.alpha * Math.min(1, perspective);
          ctx.shadowBlur = 10 * perspective;
          ctx.shadowColor = p.color;
          ctx.fill();

          // Stream connection lines back to central core
          if (rotZ < 50 && Math.random() > 0.82) {
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.lineTo(projX, projY);
            ctx.strokeStyle = p.color;
            ctx.globalAlpha = 0.12 * perspective;
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }
        }
      });

      ctx.globalAlpha = 1;
      ctx.shadowBlur = 0;

      // Central AI Intelligence Core
      ctx.save();
      ctx.translate(centerX, centerY);

      // Outer Core Halo
      const coreGradient = ctx.createRadialGradient(0, 0, 5, 0, 0, 55 * pulseScale);
      coreGradient.addColorStop(0, '#ffffff');
      coreGradient.addColorStop(0.25, '#00f0ff');
      coreGradient.addColorStop(0.6, '#3b82f6');
      coreGradient.addColorStop(0.9, '#8b5cf6');
      coreGradient.addColorStop(1, 'rgba(139, 92, 246, 0)');

      ctx.beginPath();
      ctx.arc(0, 0, 55 * pulseScale, 0, Math.PI * 2);
      ctx.fillStyle = coreGradient;
      ctx.shadowBlur = 32;
      ctx.shadowColor = '#00f0ff';
      ctx.fill();

      // Core Geometric Wireframe Ring
      ctx.rotate(globalRotation * 2);
      ctx.beginPath();
      ctx.arc(0, 0, 36, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([8, 6]);
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(0, 0, 22, 0, Math.PI * 2);
      ctx.strokeStyle = '#00f0ff';
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.stroke();

      ctx.restore();

      // Update Orbiting Cards Positions
      setCards((prevCards) =>
        prevCards.map((card) => ({
          ...card,
          angle: card.angle + card.speed,
        }))
      );

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className="relative w-full h-[540px] flex items-center justify-center overflow-hidden rounded-3xl select-none"
    >
      {/* 3D WebGL / Canvas Stage */}
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" />

      {/* Floating 3D Orbiting Document Cards */}
      <div className="absolute inset-0 pointer-events-none flex items-center justify-center perspective-1000">
        {cards.map((card) => {
          // Calculate 3D ellipse projection for each card
          const cos = Math.cos(card.angle);
          const sin = Math.sin(card.angle);
          const x = cos * card.distance + mousePos.x * 0.7;
          const z = sin * card.distance;
          const y = sin * (card.distance * 0.28) + card.heightOffset + mousePos.y * 0.5;

          const scale = 0.8 + (z + card.distance) / (card.distance * 2) * 0.35;
          const opacity = 0.65 + (z + card.distance) / (card.distance * 2) * 0.35;
          const zIndex = Math.round(z + 500);

          const IconComponent = card.icon;

          return (
            <div
              key={card.id}
              style={{
                transform: `translate3d(${x}px, ${y}px, ${z}px) scale(${scale})`,
                opacity: opacity,
                zIndex: zIndex,
              }}
              onMouseEnter={() => setActiveCard(card.id)}
              onMouseLeave={() => setActiveCard(null)}
              className={`absolute pointer-events-auto transition-transform duration-75 ease-out cursor-pointer group`}
            >
              <div
                className={`p-3.5 rounded-2xl glass-panel shadow-2xl border border-white/20 dark:border-slate-700/60 backdrop-blur-xl transition-all duration-300 hover:scale-105 ${
                  activeCard === card.id
                    ? 'ring-2 ring-cyan-400 dark:ring-cyan-400 shadow-cyan-500/30'
                    : 'hover:border-cyan-500/50'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-9 h-9 rounded-xl bg-gradient-to-tr ${card.accent} flex items-center justify-center text-white shadow-md shadow-cyan-500/20`}
                  >
                    <IconComponent className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
                      {card.name}
                      <Sparkles className="w-3 h-3 text-cyan-400 animate-pulse" />
                    </div>
                    <div className="text-[10px] text-cyan-600 dark:text-cyan-400 font-medium mt-0.5">
                      {card.tag}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Floating Center Core Label Badge */}
      <div className="absolute top-[68%] pointer-events-none flex flex-col items-center gap-1">
        <div className="px-3.5 py-1 rounded-full text-[11px] font-semibold bg-slate-900/80 dark:bg-slate-950/90 text-cyan-400 border border-cyan-500/30 shadow-lg shadow-cyan-500/20 backdrop-blur-md flex items-center gap-1.5 animate-pulse">
          <span className="w-2 h-2 rounded-full bg-cyan-400" />
          Neural Retrieval Core · Active
        </div>
      </div>
    </div>
  );
};
