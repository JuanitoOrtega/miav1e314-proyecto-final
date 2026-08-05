// La UI se sirve desde el propio contenedor de la API, así que el fetch es
// del mismo origen. Por eso no hace falta CORS ni configurar ninguna URL
// base: fue la razón de servir la interfaz desde aquí en lugar de montar un
// segundo deployment en Kubernetes.

const CAMPOS_NUMERICOS = ["tenure", "MonthlyCharges", "TotalCharges"];

const formulario = document.getElementById("formulario");
const boton = document.getElementById("boton");
const caja = document.getElementById("resultado");
const trazabilidad = document.getElementById("trazabilidad");

/** Muestra qué modelo está sirviendo, sin que nadie tenga que usar curl.
 *
 * El run_id es la pieza que vincula el servicio con el experimento que lo
 * produjo: es el mismo que figura en el Model Registry de MLflow.
 */
async function mostrarTrazabilidad() {
  try {
    const r = await fetch("/model-info");
    if (!r.ok) throw new Error("HTTP " + r.status);
    const m = await r.json();

    trazabilidad.innerHTML = `
      <span class="estado ok"><span class="luz"></span>servicio operativo</span>
      <span class="par"><span class="et">modelo</span><span class="va">${m.model_name}</span></span>
      <span class="par"><span class="et">versión</span><span class="va">${m.version}</span></span>
      <span class="par"><span class="et">alias</span><span class="va">${m.alias}</span></span>
      <span class="par"><span class="et">run</span>
        <span class="va run" title="${m.run_id}">${m.run_id}</span>
      </span>`;
  } catch (error) {
    trazabilidad.innerHTML = `
      <span class="estado mal"><span class="luz"></span>servicio no disponible</span>
      <span class="par">${error.message}</span>`;
  }
}

mostrarTrazabilidad();

/** Convierte el formulario al contrato que espera la API. */
function leerFormulario(form) {
  const datos = {};
  for (const [clave, valor] of new FormData(form).entries()) {
    datos[clave] = CAMPOS_NUMERICOS.includes(clave) ? Number(valor) : valor;
  }
  return datos;
}

/** Extrae un mensaje legible de un error 422 de Pydantic. */
async function describirError(respuesta) {
  try {
    const cuerpo = await respuesta.json();
    if (Array.isArray(cuerpo.detail)) {
      return cuerpo.detail
        .map((d) => `${d.loc?.at(-1) ?? "campo"}: ${d.msg}`)
        .join(" · ");
    }
    return cuerpo.detail ?? JSON.stringify(cuerpo);
  } catch {
    return `HTTP ${respuesta.status} ${respuesta.statusText}`;
  }
}

function mostrarPrediccion(r) {
  const porcentaje = (r.probability * 100).toFixed(1);
  const enRiesgo = r.prediction === 1;

  caja.className = enRiesgo ? "churn" : "retiene";
  caja.innerHTML = `
    <div class="prob">${porcentaje}%</div>
    <div>
      de probabilidad de abandono —
      <strong>${enRiesgo ? "cliente en riesgo" : "cliente estable"}</strong>
    </div>
    <div class="meta">
      atendido por <span class="pod">${r.served_by}</span>
      · modelo versión ${r.model_version}
    </div>`;
}

function mostrarError(mensaje) {
  caja.className = "error";
  caja.innerHTML = `<strong>Error:</strong> ${mensaje}`;
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();

  boton.disabled = true;
  boton.textContent = "Consultando…";

  try {
    const respuesta = await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(leerFormulario(evento.target)),
    });

    if (!respuesta.ok) {
      throw new Error(await describirError(respuesta));
    }

    mostrarPrediccion(await respuesta.json());
  } catch (error) {
    mostrarError(error.message);
  } finally {
    caja.style.display = "block";
    boton.disabled = false;
    boton.textContent = "Predecir";
  }
});
