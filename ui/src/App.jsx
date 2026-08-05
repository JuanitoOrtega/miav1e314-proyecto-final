import { useCallback, useEffect, useState } from "react";

import Balanceo from "./componentes/Balanceo.jsx";
import Formulario from "./componentes/Formulario.jsx";
import Resultado from "./componentes/Resultado.jsx";
import Trazabilidad from "./componentes/Trazabilidad.jsx";
import { obtenerModelo, obtenerSalud, predecir } from "./api.js";
import { VALORES_INICIALES } from "./ejemplos.js";

export default function App() {
  const [valores, setValores] = useState(VALORES_INICIALES);
  const [resultado, setResultado] = useState(null);
  const [errorPrediccion, setErrorPrediccion] = useState(null);
  const [cargando, setCargando] = useState(false);

  const [modelo, setModelo] = useState(null);
  const [errorModelo, setErrorModelo] = useState(null);
  const [saludOk, setSaludOk] = useState(null);

  // historial guarda el served_by de cada respuesta, en orden. Es la fuente del
  // panel de balanceo; vive solo en memoria, se pierde al recargar a propósito.
  const [historial, setHistorial] = useState([]);

  const consultarEstado = useCallback(async () => {
    try {
      await obtenerSalud();
      setSaludOk(true);
    } catch {
      setSaludOk(false);
    }
    try {
      setModelo(await obtenerModelo());
      setErrorModelo(null);
    } catch (error) {
      setModelo(null);
      setErrorModelo(error.message);
    }
  }, []);

  useEffect(() => {
    consultarEstado();
  }, [consultarEstado]);

  const cambiarCampo = useCallback((nombre, valor) => {
    setValores((previos) => ({ ...previos, [nombre]: valor }));
  }, []);

  const cargarEjemplo = useCallback((ejemplo) => {
    setValores(ejemplo.valores);
    setResultado(null);
    setErrorPrediccion(null);
  }, []);

  const enviar = useCallback(async () => {
    setCargando(true);
    setErrorPrediccion(null);
    try {
      const respuesta = await predecir(valores);
      setResultado(respuesta);
      setHistorial((previos) => [...previos, respuesta.served_by]);
    } catch (error) {
      setResultado(null);
      setErrorPrediccion(error.message);
    } finally {
      setCargando(false);
    }
  }, [valores]);

  return (
    <div className="pagina">
      <header className="cabecera">
        <div>
          <h1>Predicción de abandono de clientes</h1>
          <p className="subtitulo">
            Consume <code>POST /predict</code> del servicio desplegado en
            Kubernetes. Modelo cargado del Model Registry de MLflow por alias.
          </p>
        </div>
        <p className={`estado ${saludOk === false ? "es-critico" : saludOk ? "es-bueno" : ""}`}>
          <span className="punto" aria-hidden="true" />
          {saludOk === null && "Comprobando servicio…"}
          {saludOk === true && "Servicio respondiendo"}
          {saludOk === false && "Servicio no responde"}
        </p>
      </header>

      <div className="columnas">
        <Formulario
          valores={valores}
          onCambio={cambiarCampo}
          onEjemplo={cargarEjemplo}
          onEnviar={enviar}
          cargando={cargando}
        />

        <div className="lateral">
          <Resultado resultado={resultado} error={errorPrediccion} />
          <Trazabilidad modelo={modelo} error={errorModelo} />
        </div>
      </div>

      <Balanceo historial={historial} onLimpiar={() => setHistorial([])} />

      <footer className="pie">
        MOD14 · Maestría en Ciencia de Datos e Inteligencia Artificial, UAGRM
      </footer>
    </div>
  );
}
