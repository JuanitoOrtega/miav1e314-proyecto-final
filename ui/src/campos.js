// Definición declarativa de las 19 variables de entrada del modelo.
//
// Es el espejo exacto de CustomerFeatures en src/api/schemas.py: los valores de
// cada opción son los Literal de Pydantic, sin traducir. Lo que se traduce es
// solo la etiqueta que ve la persona. Si el esquema cambia, este fichero es el
// único sitio de la UI que hay que tocar.
//
// Ojo con SeniorCitizen: el esquema declara Literal["0", "1"], es decir cadena
// y no entero. Se envía tal cual; convertirlo a número da un 422.

// El valor viaja en inglés porque así lo declara el esquema; solo se traduce
// el texto que se muestra.
const SI_NO = [
  { valor: "Yes", texto: "Sí" },
  { valor: "No", texto: "No" },
];

const SI_NO_SIN_INTERNET = [
  { valor: "Yes", texto: "Sí" },
  { valor: "No", texto: "No" },
  { valor: "No internet service", texto: "Sin servicio de internet" },
];

export const CAMPOS = [
  // --- Numéricas ---
  {
    nombre: "tenure",
    etiqueta: "Antigüedad",
    ayuda: "meses como cliente",
    tipo: "numero",
    min: 0,
    max: 100,
    paso: 1,
  },
  {
    nombre: "MonthlyCharges",
    etiqueta: "Cargo mensual",
    ayuda: "importe facturado al mes",
    tipo: "numero",
    min: 0,
    paso: 0.01,
  },
  {
    nombre: "TotalCharges",
    etiqueta: "Cargo total",
    ayuda: "importe acumulado histórico",
    tipo: "numero",
    min: 0,
    paso: 0.01,
  },

  // --- Perfil del cliente ---
  {
    nombre: "gender",
    etiqueta: "Género",
    tipo: "opcion",
    opciones: [
      { valor: "Female", texto: "Mujer" },
      { valor: "Male", texto: "Hombre" },
    ],
  },
  {
    nombre: "SeniorCitizen",
    etiqueta: "Tercera edad",
    tipo: "opcion",
    opciones: [
      { valor: "0", texto: "No" },
      { valor: "1", texto: "Sí" },
    ],
  },
  {
    nombre: "Partner",
    etiqueta: "Tiene pareja",
    tipo: "opcion",
    opciones: SI_NO,
  },
  {
    nombre: "Dependents",
    etiqueta: "Tiene dependientes",
    tipo: "opcion",
    opciones: SI_NO,
  },

  // --- Servicios contratados ---
  {
    nombre: "PhoneService",
    etiqueta: "Servicio telefónico",
    tipo: "opcion",
    opciones: SI_NO,
  },
  {
    nombre: "MultipleLines",
    etiqueta: "Líneas múltiples",
    tipo: "opcion",
    opciones: [
      { valor: "Yes", texto: "Sí" },
      { valor: "No", texto: "No" },
      { valor: "No phone service", texto: "Sin servicio telefónico" },
    ],
  },
  {
    nombre: "InternetService",
    etiqueta: "Servicio de internet",
    tipo: "opcion",
    opciones: [
      { valor: "Fiber optic", texto: "Fibra óptica" },
      { valor: "DSL", texto: "DSL" },
      { valor: "No", texto: "No" },
    ],
  },
  {
    nombre: "OnlineSecurity",
    etiqueta: "Seguridad en línea",
    tipo: "opcion",
    opciones: SI_NO_SIN_INTERNET,
  },
  {
    nombre: "OnlineBackup",
    etiqueta: "Copia de seguridad",
    tipo: "opcion",
    opciones: SI_NO_SIN_INTERNET,
  },
  {
    nombre: "DeviceProtection",
    etiqueta: "Protección de dispositivo",
    tipo: "opcion",
    opciones: SI_NO_SIN_INTERNET,
  },
  {
    nombre: "TechSupport",
    etiqueta: "Soporte técnico",
    tipo: "opcion",
    opciones: SI_NO_SIN_INTERNET,
  },
  {
    nombre: "StreamingTV",
    etiqueta: "Streaming de TV",
    tipo: "opcion",
    opciones: SI_NO_SIN_INTERNET,
  },
  {
    nombre: "StreamingMovies",
    etiqueta: "Streaming de películas",
    tipo: "opcion",
    opciones: SI_NO_SIN_INTERNET,
  },

  // --- Contrato y facturación ---
  {
    nombre: "Contract",
    etiqueta: "Tipo de contrato",
    tipo: "opcion",
    opciones: [
      { valor: "Month-to-month", texto: "Mes a mes" },
      { valor: "One year", texto: "Un año" },
      { valor: "Two year", texto: "Dos años" },
    ],
  },
  {
    nombre: "PaperlessBilling",
    etiqueta: "Facturación sin papel",
    tipo: "opcion",
    opciones: SI_NO,
  },
  {
    nombre: "PaymentMethod",
    etiqueta: "Método de pago",
    tipo: "opcion",
    opciones: [
      { valor: "Electronic check", texto: "Cheque electrónico" },
      { valor: "Mailed check", texto: "Cheque por correo" },
      { valor: "Bank transfer (automatic)", texto: "Transferencia (automática)" },
      { valor: "Credit card (automatic)", texto: "Tarjeta de crédito (automática)" },
    ],
  },
];

/** Los tres campos que viajan como número en el JSON. El resto son cadenas. */
export const NUMERICOS = CAMPOS.filter((c) => c.tipo === "numero").map((c) => c.nombre);

/** Agrupación visual del formulario. Los nombres deben existir en CAMPOS. */
export const GRUPOS = [
  { titulo: "Contrato y facturación", campos: ["Contract", "PaymentMethod", "PaperlessBilling", "MonthlyCharges", "TotalCharges", "tenure"] },
  { titulo: "Perfil del cliente", campos: ["gender", "SeniorCitizen", "Partner", "Dependents"] },
  { titulo: "Servicios contratados", campos: ["PhoneService", "MultipleLines", "InternetService", "OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies"] },
];
