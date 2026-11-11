import React from 'react';

/** Hard-hat + beam brand mark. */
export function BrandMark({ size = 38 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <rect width="40" height="40" rx="10" fill="#f2a900" />
      <path d="M8 27h24v-2.4A2.6 2.6 0 0 0 29.4 22H10.6A2.6 2.6 0 0 0 8 24.6z" fill="#111c28" />
      <path d="M11 22v-2.5a9 9 0 0 1 6.2-8.55M22.8 10.95A9 9 0 0 1 29 19.5V22" stroke="#111c28" strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <rect x="17.4" y="9" width="5.2" height="10" rx="1.2" fill="#111c28" />
      <path d="M6 31h28" stroke="#111c28" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}

/** Line-art site scene: tower crane, bridge, road under construction. */
export function SiteScene({ className }: { className?: string }) {
  const s = 'rgba(197,214,232,.55)';
  const a = '#f2a900';
  return (
    <svg className={className} viewBox="0 0 600 380" fill="none" role="img" aria-label="Illustration of a construction site with a tower crane, bridge and road">
      {/* sun / ground */}
      <circle cx="120" cy="96" r="42" stroke={a} strokeOpacity=".35" strokeWidth="2" />
      <path d="M0 300h600" stroke={s} strokeWidth="2" />
      {/* buildings under construction */}
      <g stroke={s} strokeWidth="1.6">
        <rect x="40" y="190" width="70" height="110" />
        <path d="M40 217h70M40 245h70M40 272h70M63 190v110M87 190v110" strokeOpacity=".6" />
        <rect x="118" y="150" width="58" height="150" />
        <path d="M118 180h58M118 210h58M118 240h58M118 270h58" strokeOpacity=".6" />
        <path d="M118 150l58 30M176 150l-58 30M118 180l58 30M176 180l-58 30" strokeOpacity=".35" />
      </g>
      {/* tower crane */}
      <g stroke="#e6edf5" strokeWidth="2" strokeLinejoin="round">
        <path d="M398 300V92M420 300V92" />
        {[0, 1, 2, 3, 4, 5, 6, 7].map(i => <path key={i} d={`M398 ${300 - i * 26}L420 ${274 - i * 26}M420 ${300 - i * 26}L398 ${274 - i * 26}`} strokeWidth="1.2" strokeOpacity=".7" />)}
        <path d="M398 92h22l-11-26z" />
        <path d="M300 92h230M300 104h230" />
        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map(i => <path key={i} d={`M${300 + i * 19} 104l9.5-12 9.5 12`} strokeWidth="1.1" strokeOpacity=".7" />)}
        <path d="M409 66l-100 26M409 66l110 26" strokeWidth="1.2" />
      </g>
      <rect x="490" y="104" width="30" height="20" rx="2" fill="#111c28" stroke="#e6edf5" strokeWidth="2" />
      <rect x="402" y="128" width="14" height="14" fill={a} />
      {/* hook + load (steel beam) */}
      <path d="M332 104v120" stroke="#e6edf5" strokeWidth="1.4" />
      <path d="M328 224h8l-4 8z" fill={a} />
      <path d="M332 232l-26 14M332 232l26 14" stroke="#e6edf5" strokeWidth="1.2" />
      <rect x="290" y="246" width="84" height="10" fill={a} />
      <path d="M290 246h84M290 256h84" stroke="#111c28" strokeWidth="1" />
      {/* bridge */}
      <g stroke={s} strokeWidth="1.8">
        <path d="M200 262h400" stroke="#e6edf5" strokeWidth="3" />
        <path d="M230 262v38M310 262v38M470 262v38M550 262v38" />
        <path d="M230 300a40 30 0 0 1 80 0M470 300a40 30 0 0 1 80 0" strokeOpacity=".7" />
      </g>
      {/* road in perspective */}
      <path d="M240 380 290 300h60l70 80z" fill="rgba(255,255,255,.04)" stroke={s} strokeWidth="1.6" />
      <path d="M322 306v10M324 328v14M327 356v18" stroke={a} strokeWidth="3" strokeLinecap="round" />
      {/* barriers */}
      <g>
        <rect x="440" y="318" width="54" height="12" rx="2" fill={a} />
        <path d="M448 318l-8 12M462 318l-8 12M476 318l-8 12M490 318l-8 12" stroke="#111c28" strokeWidth="4" />
        <path d="M446 330v14M488 330v14" stroke="#e6edf5" strokeWidth="2" />
        <path d="M150 340l12-34 12 34z" fill={a} />
        <path d="M154 330h16M158 318h8" stroke="#fff" strokeWidth="3" />
        <path d="M144 342h36" stroke="#e6edf5" strokeWidth="2.5" strokeLinecap="round" />
      </g>
    </svg>
  );
}
