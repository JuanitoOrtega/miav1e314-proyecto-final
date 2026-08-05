import { CAMPOS, GRUPOS } from "../campos.js";
import { EJEMPLOS } from "../ejemplos.js";

const POR_NOMBRE = Object.fromEntries(CAMPOS.map((campo) => [campo.nombre, campo]));

/** Las opciones se declaran como cadena suelta o como {valor, texto}. */
function normalizar(opcion) {
  return typeof opcion === "string" ? { valor: opcion, texto: opcion } : opcion;
}

function Campo({ campo, valor, onCambio }) {
  const id = `campo-${campo.nombre}`;
  const idAyuda = campo.ayuda ? `${id}-ayuda` : undefined;

  return (
    <div className="campo">
      <label htmlFor={id}>{campo.etiqueta}</label>

      {campo.tipo === "numero" ? (
        <input
          id={id}
          type="number"
          value={valor}
          min={campo.min}
          max={campo.max}
          step={campo.paso}
          required
          aria-describedby={idAyuda}
          onChange={(evento) => onCambio(campo.nombre, evento.target.value)}
        />
      ) : (
        <select
          id={id}
          value={valor}
          aria-describedby={idAyuda}
          onChange={(evento) => onCambio(campo.nombre, evento.target.value)}
        >
          {campo.opciones.map(normalizar).map((opcion) => (
            <option key={opcion.valor} value={opcion.valor}>
              {opcion.texto}
            </option>
          ))}
        </select>
      )}

      {campo.ayuda && (
        <span className="ayuda" id={idAyuda}>
          {campo.ayuda}
        </span>
      )}
    </div>
  );
}

export default function Formulario({ valores, onCambio, onEjemplo, onEnviar, cargando }) {
  return (
    <form
      className="panel formulario"
      onSubmit={(evento) => {
        evento.preventDefault();
        onEnviar();
      }}
    >
      <div className="ejemplos">
        <span className="ejemplos-titulo">Cargar un perfil de ejemplo</span>
        <div className="ejemplos-botones">
          {EJEMPLOS.map((ejemplo) => (
            <button
              key={ejemplo.id}
              type="button"
              className="boton-secundario"
              title={ejemplo.descripcion}
              onClick={() => onEjemplo(ejemplo)}
            >
              {ejemplo.titulo}
            </button>
          ))}
        </div>
      </div>

      {GRUPOS.map((grupo) => (
        <fieldset key={grupo.titulo}>
          <legend>{grupo.titulo}</legend>
          <div className="rejilla">
            {grupo.campos.map((nombre) => (
              <Campo
                key={nombre}
                campo={POR_NOMBRE[nombre]}
                valor={valores[nombre]}
                onCambio={onCambio}
              />
            ))}
          </div>
        </fieldset>
      ))}

      <button type="submit" className="boton-principal" disabled={cargando}>
        {cargando ? "Consultando…" : "Predecir abandono"}
      </button>
    </form>
  );
}
