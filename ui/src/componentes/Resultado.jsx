// El veredicto de una predicción.
//
// La probabilidad es una razón contra un límite (el umbral de decisión de 0.5),
// así que la forma correcta es un medidor, no un gráfico. El color de estado
// nunca va solo: siempre lo acompañan un icono y una etiqueta de texto, porque
// los pasos "good" y "critical" quedan a ΔE 4.1 bajo deuteranopía y el color
// por sí mismo no distingue los dos casos.

const UMBRAL = 0.5;

function IconoRiesgo() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">
      <path
        d="M8 1.5 15 14.5H1L8 1.5Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M8 6v3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="8" cy="12" r="0.9" fill="currentColor" />
    </svg>
  );
}

function IconoEstable() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">
      <circle cx="8" cy="8" r="6.7" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M5 8.2 7.2 10.4 11 5.9"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function Resultado({ resultado, error }) {
  if (error) {
    return (
      <section className="panel resultado" aria-live="polite">
        <h2>Resultado</h2>
        <p className="mensaje-error">
          <strong>No se pudo predecir.</strong> {error}
        </p>
      </section>
    );
  }

  if (!resultado) {
    return (
      <section className="panel resultado" aria-live="polite">
        <h2>Resultado</h2>
        <p className="vacio">
          Rellena el formulario y pulsa <em>Predecir abandono</em>. Cada respuesta
          indica qué pod la atendió.
        </p>
      </section>
    );
  }

  const enRiesgo = resultado.prediction === 1;
  const porcentaje = resultado.probability * 100;

  return (
    <section className="panel resultado" aria-live="polite">
      <h2>Resultado</h2>

      <p className={`veredicto ${enRiesgo ? "es-critico" : "es-bueno"}`}>
        {enRiesgo ? <IconoRiesgo /> : <IconoEstable />}
        <span>{enRiesgo ? "Cliente en riesgo de abandono" : "Cliente estable"}</span>
      </p>

      <p className="cifra-hero">{porcentaje.toFixed(1)}%</p>
      <p className="cifra-pie">probabilidad de abandono</p>

      <div
        className="medidor"
        role="meter"
        aria-valuenow={Number(porcentaje.toFixed(1))}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Probabilidad de abandono"
      >
        <div
          className={`medidor-relleno ${enRiesgo ? "es-critico" : "es-bueno"}`}
          style={{ width: `${Math.min(100, Math.max(0, porcentaje))}%` }}
        />
        <div className="medidor-umbral" style={{ left: `${UMBRAL * 100}%` }} />
      </div>
      <p className="medidor-nota">
        La marca es el umbral de decisión, {UMBRAL.toFixed(2)}: por encima, el
        servicio devuelve <code>prediction: 1</code>.
      </p>

      <dl className="detalle">
        <div>
          <dt>Atendido por</dt>
          <dd>
            <code>{resultado.served_by}</code>
          </dd>
        </div>
        <div>
          <dt>Versión del modelo</dt>
          <dd>
            <code>{resultado.model_version}</code>
          </dd>
        </div>
      </dl>
    </section>
  );
}
