// Perfiles precargados para la demostración en vivo.
//
// Existen para que en la defensa no haya que rellenar 19 campos a mano delante
// del docente. El perfil de riesgo combina los factores que el modelo aprendió
// como predictores fuertes de abandono (contrato mes a mes, poca antigüedad,
// fibra, cheque electrónico); el estable, los contrarios.

export const EJEMPLOS = [
  {
    id: "riesgo",
    titulo: "Cliente en riesgo",
    descripcion: "Contrato mes a mes, 2 meses de antigüedad, fibra, cheque electrónico",
    valores: {
      tenure: 2,
      MonthlyCharges: 89.9,
      TotalCharges: 179.8,
      gender: "Female",
      SeniorCitizen: "1",
      Partner: "No",
      Dependents: "No",
      PhoneService: "Yes",
      MultipleLines: "No",
      InternetService: "Fiber optic",
      OnlineSecurity: "No",
      OnlineBackup: "No",
      DeviceProtection: "No",
      TechSupport: "No",
      StreamingTV: "Yes",
      StreamingMovies: "Yes",
      Contract: "Month-to-month",
      PaperlessBilling: "Yes",
      PaymentMethod: "Electronic check",
    },
  },
  {
    id: "estable",
    titulo: "Cliente estable",
    descripcion: "Contrato de dos años, 6 años de antigüedad, DSL, pago automático",
    valores: {
      tenure: 72,
      MonthlyCharges: 60.15,
      TotalCharges: 4330.8,
      gender: "Male",
      SeniorCitizen: "0",
      Partner: "Yes",
      Dependents: "Yes",
      PhoneService: "Yes",
      MultipleLines: "Yes",
      InternetService: "DSL",
      OnlineSecurity: "Yes",
      OnlineBackup: "Yes",
      DeviceProtection: "Yes",
      TechSupport: "Yes",
      StreamingTV: "No",
      StreamingMovies: "No",
      Contract: "Two year",
      PaperlessBilling: "No",
      PaymentMethod: "Bank transfer (automatic)",
    },
  },
];

/** El perfil con el que arranca el formulario. */
export const VALORES_INICIALES = EJEMPLOS[0].valores;
