// Panel de trazabilidad.
//
// Existe por el §3.3 del enunciado: hay que poder demostrar que el modelo que
// atiende peticiones es el del experimento que se enseña en MLflow. Mostrar el
// run_id aquí permite compararlo con el del Model Registry sin salir a la
// terminal, que es justo la pregunta de la defensa.

export default function Trazabilidad({ modelo, error }) {
  return (
    <section className="panel trazabilidad">
      <h2>Modelo en servicio</h2>

      {error && (
        <p className="mensaje-error">
          <strong>Sin información del modelo.</strong> {error}
        </p>
      )}

      {!error && !modelo && <p className="vacio">Consultando <code>/model-info</code>…</p>}

      {modelo && (
        <>
          <dl className="detalle">
            <div>
              <dt>Nombre registrado</dt>
              <dd>
                <code>{modelo.model_name}</code>
              </dd>
            </div>
            <div>
              <dt>Versión</dt>
              <dd>
                <code>{modelo.version}</code>
              </dd>
            </div>
            <div>
              <dt>Alias</dt>
              <dd>
                <code>{modelo.alias}</code>
              </dd>
            </div>
            <div>
              <dt>Run de origen</dt>
              <dd>
                <code className="run-id">{modelo.run_id}</code>
              </dd>
            </div>
          </dl>
          <p className="nota">
            El pod cargó <code>models:/{modelo.model_name}@{modelo.alias}</code> del
            Model Registry. Ese <code>run_id</code> es el del run que produjo el
            modelo: el mismo que aparece en MLflow.
          </p>
        </>
      )}
    </section>
  );
}
