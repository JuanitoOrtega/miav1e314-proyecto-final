// La UI se sirve desde el propio contenedor de la API, así que el fetch es
// del mismo origen: no hace falta CORS ni configurar ninguna URL base.

const NUMERICOS = ["tenure", "MonthlyCharges", "TotalCharges"];

document.getElementById("formulario").addEventListener("submit", async (evento) => {
  evento.preventDefault();

  const boton = document.getElementById("boton");
  const caja = document.getElementById("resultado");
  boton.disabled = true;
  boton.textContent = "Consultando…";

  const datos = {};
  for (const [clave, valor] of new FormData(evento.target).entries()) {
    datos[clave] = NUMERICOS.includes(clave) ? Number(valor) : valor;
  }

  try {
    const respuesta = await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    });

    if (!respuesta.ok) {
      const detalle = await respuesta.text();
      throw new Error(`HTTP ${respuesta.status} — ${detalle}`);
    }

    const r = await respuesta.json();
    const pct = (r.probability * 100).toFixed(1);

    caja.className = r.prediction === 1 ? "churn" : "retiene";
    caja.innerHTML = `
      <div class="prob">${pct}%</div>
      <div>de probabilidad de abandono —
        <strong>${r.prediction === 1 ? "cliente en riesgo" : "cliente estable"}</strong>
      </div>
      <div class="meta">
        atendido por <span class="pod">${r.served_by}</span>
        · modelo versión ${r.model_version}
      </div>`;
  } catch (error) {
    caja.className = "error";
    caja.innerHTML = `<strong>Error:</strong> ${error.message}`;
  } finally {
    caja.style.display = "block";
    boton.disabled = false;
    boton.textContent = "Predecir";
  }
});
