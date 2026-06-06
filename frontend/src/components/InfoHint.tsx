type InfoHintAlign = "left" | "center" | "right";

export default function InfoHint({
  text,
  className = "",
  align: _align = "center"
}: {
  text: string;
  className?: string;
  align?: InfoHintAlign;
}) {
  return (
    <button
      type="button"
      className={`info-hint ${className}`.trim()}
      aria-label={text}
      title={text}
    >
      <span className="info-hint__icon" aria-hidden="true">
        ?
      </span>
    </button>
  );
}
