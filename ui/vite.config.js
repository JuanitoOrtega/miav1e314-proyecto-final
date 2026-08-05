import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// El build escribe directamente en src/api/static/, que es el directorio que
// main.py monta con StaticFiles. Consecuencias buscadas:
//
//   - El artefacto compilado se commitea, así que `uvicorn src.api.main:app`
//     y `docker build` siguen funcionando sin Node instalado. El Dockerfile
//     no cambia y el build de la imagen en el VPS sigue sin depender de la red.
//   - El origen del fetch sigue siendo el mismo que el de la API, así que no
//     hace falta CORS ni una URL base configurable.
//
// El precio es tener el bundle en git. Se asume a conciencia: la alternativa
// (una etapa de Node en el Dockerfile) metería `npm ci` en la ruta de
// despliegue del VPS, que es justo lo que no queremos tocar antes de entregar.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/api/static",
    emptyOutDir: true,
  },
  server: {
    // En desarrollo (`npm run dev`) la UI vive en el 5173 y la API en el 8000.
    // El proxy reproduce el mismo origen que hay en producción, para que el
    // código de fetch sea idéntico en los dos entornos.
    proxy: {
      "/predict": "http://localhost:8000",
      "/model-info": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/ready": "http://localhost:8000",
    },
  },
});
