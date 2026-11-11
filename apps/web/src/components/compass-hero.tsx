/** The hero compass: four bearings are the four things Compassio helps you do. */
export function CompassHero() {
  const ticks = Array.from({ length: 72 }, (_, i) => i * 5);
  const bearings: Array<[number, string]> = [
    [0, "Find"],
    [90, "Understand"],
    [180, "Plan"],
    [270, "Compare"],
  ];
  return (
    <svg viewBox="-80 -6 560 412" className="w-full max-w-[32rem]" role="img" aria-label="Compass with four bearings: find, understand, compare, plan">
      <circle cx="200" cy="200" r="168" fill="none" stroke="#2c5446" strokeWidth="1" />
      <circle cx="200" cy="200" r="120" fill="none" stroke="#2c5446" strokeWidth="1" strokeDasharray="2 6" />
      {ticks.map((deg) => {
        const long = deg % 90 === 0;
        const mid = deg % 30 === 0;
        const r1 = long ? 146 : mid ? 154 : 160;
        const rad = (deg * Math.PI) / 180;
        return (
          <line
            key={deg}
            x1={200 + r1 * Math.sin(rad)}
            y1={200 - r1 * Math.cos(rad)}
            x2={200 + 168 * Math.sin(rad)}
            y2={200 - 168 * Math.cos(rad)}
            stroke={long ? "#a9c2b5" : "#3c6a59"}
            strokeWidth={long ? 2 : 1}
          />
        );
      })}
      {bearings.map(([deg, label]) => {
        const rad = (deg * Math.PI) / 180;
        const r = 188;
        const x = 200 + r * Math.sin(rad);
        const y = 200 - r * Math.cos(rad) + 5;
        return (
          <text key={label} x={x} y={y} textAnchor="middle" fontSize="15" fontWeight="600" fill="#e8f0ea">
            {label}
          </text>
        );
      })}
      <g
        className="needle-settle"
        style={{ ["--needle-from" as string]: "-140deg", ["--needle-to" as string]: "28deg", transformOrigin: "200px 200px" }}
      >
        <path d="M200 70 L214 200 L200 214 L186 200 Z" fill="#1d6b4f" />
        <path d="M200 70 L214 200 L200 200 Z" fill="#7fd1a3" />
        <path d="M200 330 L214 200 L200 186 L186 200 Z" fill="#2c5446" />
      </g>
      <circle cx="200" cy="200" r="9" fill="#0f2a22" stroke="#7fd1a3" strokeWidth="3" />
    </svg>
  );
}
