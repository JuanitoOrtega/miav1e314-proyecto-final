// Cliente de la API.
//
// Todas las rutas son relativas a propósito: la UI compilada la sirve el propio
// contenedor de la API (main.py monta StaticFiles en "/"), así que el origen es
// el mismo y no hace falta CORS ni una URL base configurable. En desarrollo,
// el proxy de vite.config.js reproduce esa misma condición.

import { NUMERICOS } from "./campos.js";

/** Convierte los valores del formulario al JSON que espera CustomerFeatures. */
export function aPayload(valores) {
  const payload = {};
  for (const [clave, valor] of Object.entries(valores)) {
    payload[clave] = NUMERICOS.includes(clave) ? Number(valor) : String(valor);
  }
  return payload;
}

async function leerError(respuesta) {
  // FastAPI devuelve {"detail": ...}: un texto en los 503 y una lista de
  // errores de validación en los 422. Se distinguen para que el mensaje sea
  // accionable en lugar de un volcado de JSON.
  let detalle;
  try {
    const cuerpo = await respuesta.json();
    detalle = cuerpo.detail;
  } catch {
    detalle = await respuesta.text().catch(() => "");
  }

  if (Array.isArray(detalle)) {
    const campos = detalle
      .map((e) => (Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : null))
      .filter(Boolean);
    return `Datos rechazados por la API (422) en: ${campos.join(", ")}`;
  }
  if (respuesta.status === 503) {
    return "El pod respondió 503: todavía no ha cargado el modelo desde MLflow.";
  }
  return `HTTP ${respuesta.status} — ${detalle || respuesta.statusText}`;
}

export async function predecir(valores) {
  const respuesta = await fetch("/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(aPayload(valores)),
  });
  if (!respuesta.ok) throw new Error(await leerError(respuesta));
  return respuesta.json();
}

export async function obtenerModelo() {
  const respuesta = await fetch("/model-info");
  if (!respuesta.ok) throw new Error(await leerError(respuesta));
  return respuesta.json();
}

export async function obtenerSalud() {
  const respuesta = await fetch("/health");
  if (!respuesta.ok) throw new Error(await leerError(respuesta));
  return respuesta.json();
}
