"""Contratos de entrada y salida de la API."""
from typing import Literal

from pydantic import BaseModel, Field


class CustomerFeatures(BaseModel):
    """Las 19 variables de entrada del modelo."""

    # Numéricas
    tenure: int = Field(..., ge=0, le=100, description="Meses de antigüedad")
    MonthlyCharges: float = Field(..., ge=0, description="Cargo mensual")
    TotalCharges: float = Field(..., ge=0, description="Cargo total acumulado")

    # Categóricas
    gender: Literal["Male", "Female"]
    SeniorCitizen: Literal["0", "1"]
    Partner: Literal["Yes", "No"]
    Dependents: Literal["Yes", "No"]
    PhoneService: Literal["Yes", "No"]
    MultipleLines: Literal["Yes", "No", "No phone service"]
    InternetService: Literal["DSL", "Fiber optic", "No"]
    OnlineSecurity: Literal["Yes", "No", "No internet service"]
    OnlineBackup: Literal["Yes", "No", "No internet service"]
    DeviceProtection: Literal["Yes", "No", "No internet service"]
    TechSupport: Literal["Yes", "No", "No internet service"]
    StreamingTV: Literal["Yes", "No", "No internet service"]
    StreamingMovies: Literal["Yes", "No", "No internet service"]
    Contract: Literal["Month-to-month", "One year", "Two year"]
    PaperlessBilling: Literal["Yes", "No"]
    PaymentMethod: Literal[
        "Electronic check",
        "Mailed check",
        "Bank transfer (automatic)",
        "Credit card (automatic)",
    ]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tenure": 12, "MonthlyCharges": 70.35, "TotalCharges": 844.20,
                    "gender": "Female", "SeniorCitizen": "0", "Partner": "Yes",
                    "Dependents": "No", "PhoneService": "Yes",
                    "MultipleLines": "No", "InternetService": "Fiber optic",
                    "OnlineSecurity": "No", "OnlineBackup": "Yes",
                    "DeviceProtection": "No", "TechSupport": "No",
                    "StreamingTV": "Yes", "StreamingMovies": "No",
                    "Contract": "Month-to-month", "PaperlessBilling": "Yes",
                    "PaymentMethod": "Electronic check",
                }
            ]
        }
    }


class PredictionResponse(BaseModel):
    prediction: int
    probability: float
    served_by: str
    model_version: str


class ModelInfo(BaseModel):
    model_name: str
    version: str
    run_id: str
    alias: str
    loaded_at: str