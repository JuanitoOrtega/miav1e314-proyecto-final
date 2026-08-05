// Reparto de peticiones entre los pods del Deployment.
//
// El §5.2 del enunciado exige demostrar que peticiones sucesivas al Service las
// atienden pods distintos. La API ya devuelve served_by (el POD_NAME que le
// inyecta la Downward API); aquí solo se acumula por pod dentro de la sesión.
//
// Decisiones de la visualización:
//   - Barras y no tarta: el trabajo del lector es comparar magnitudes.
//   - Una sola serie ("peticiones atendidas"), luego un solo tono y sin leyenda;
//     la identidad la lleva el nombre del pod escrito al lado, no el color.
//   - El valor va etiquetado en la punta de cada barra, así que el panel se lee
//     igual sin percibir el color.

export default function Balanceo({ historial, onLimpiar }) {
  const total = historial.length;

  // Un Map conserva el orden de primera aparición: los pods no bailan de
  // posición al llegar peticiones nuevas, que haría ilegible la comparación.
  const conteo = new Map();
  for (const pod of historial) conteo.set(pod, (conteo.get(pod) ?? 0) + 1);

  const filas = [...conteo.entries()].map(([pod, peticiones]) => ({
    pod,
    peticiones,
    porcentaje: total === 0 ? 0 : (peticiones / total) * 100,
  }));

  const maximo = Math.max(1, ...filas.map((f) => f.peticiones));

  return (
    <section className="panel balanceo">
      <div className="balanceo-cabecera">
        <div>
          <h2>Reparto entre réplicas</h2>
          <p className="subtitulo">
            Peticiones de esta sesión, por pod que las atendió. Pulsa
            <em> Predecir</em> varias veces: el Service reparte entre las réplicas.
          </p>
        </div>
        {total > 0 && (
          <button type="button" className="boton-secundario" onClick={onLimpiar}>
            Reiniciar cuenta
          </button>
        )}
      </div>

      <div className="kpis">
        <div className="kpi">
          <span className="kpi-etiqueta">Peticiones</span>
          <span className="kpi-valor">{total}</span>
        </div>
        <div className="kpi">
          <span className="kpi-etiqueta">Pods distintos</span>
          <span className="kpi-valor">{filas.length}</span>
        </div>
      </div>

      {total === 0 ? (
        <p className="vacio">Todavía no hay peticiones que repartir.</p>
      ) : (
        <ul className="barras">
          {filas.map((fila) => (
            <li key={fila.pod} title={`${fila.pod}: ${fila.peticiones} de ${total}`}>
              <span className="barra-etiqueta" lang="en">
                {fila.pod}
              </span>
              <span className="barra-pista">
                <span
                  className="barra-marca"
                  style={{ width: `${(fila.peticiones / maximo) * 100}%` }}
                />
              </span>
              <span className="barra-valor">
                {fila.peticiones}
                <span className="barra-porcentaje">{fila.porcentaje.toFixed(0)}%</span>
              </span>
            </li>
          ))}
        </ul>
      )}

      {filas.length === 1 && total > 2 && (
        <p className="nota">
          Todas las respuestas vienen del mismo pod. Si estás probando con
          <code> kubectl port-forward</code>, es lo esperado: el reenvío se fija a
          una réplica y no balancea. La demostración hay que hacerla contra el
          NodePort o desde un pod cliente dentro del clúster.
        </p>
      )}
    </section>
  );
}
