# herdr-valet

Aparca las sesiones de [Claude Code](https://claude.com/claude-code) que llevan días quietas en
[herdr](https://herdr.dev) y te las devuelve con un resumen de en qué estabas.

Una sesión quieta no hace nada, pero Claude más sus MCP pesan entre 0,5 y 1,2 GB. Se dejan
abiertas para no olvidar en qué se estaba, y con 30 abiertas se llena la swap. herdr-valet:

1. **Aparca:** Haiku escribe una ficha (título, en qué estábamos, qué quedó pendiente, próximo
   paso) con la carpeta, la rama y el modelo. Recién después cierra el panel.
2. **Aparca solo:** cada 10 min, lo que lleva más de `idle_days` (3) quieto. Nunca una sesión
   trabajando, esperando una respuesta o enfocada.
3. **Sobrevive a un reinicio:** guarda una foto de lo abierto. Si la máquina se reinicia, cada
   sesión que no volvió recibe su ficha ("cortada por un reinicio").
4. **Página web** (`127.0.0.1:8790`): las aparcadas con su resumen y un botón **Reanudar en
   herdr**, las abiertas con **Aparcar**, y las reanudadas hace poco. Sirve desde el celular.

Reanudar abre un workspace en herdr con `claude --resume <id>`: vuelve la conversación entera,
la ficha es solo el índice.

## Requisitos

- herdr con la integración de Claude (`herdr integration status` → `claude`): de ahí sale el id
  de sesión de cada panel. Probado con herdr 0.7.1.
- Claude Code (`claude` en el PATH).
- Python 3.9 o más nuevo, solo biblioteca estándar. Linux (systemd) o macOS (launchd).

## Instalar

```sh
git clone https://github.com/renatogm24/herdr-valet ~/herdr-valet
~/herdr-valet/install.sh
```

Re-correr `install.sh` después de un `git pull`. `install.sh --uninstall` saca servicios y
comando; las fichas y la config quedan.

## Usar

- Página: `http://127.0.0.1:8790` (el puerto es `8790 + (uid - 1000)`; en macOS, 8790).
- CLI: `herdr-valet live`, `list`, `park <pane_id>`, `resume <session_id>`,
  `auto --dry-run` (qué aparcaría), `config`.

## Configuración

`~/.config/herdr-valet/config.toml`, ver [`config.example.toml`](config.example.toml). Lo más
útil es `resume_command`: si lanzás Claude con un wrapper (secretos de MCP, flags, otra cuenta),
ponelo ahí para que la sesión vuelva igual que como se abrió. `summary_command` hace lo mismo
para los resúmenes: si una sesión era de una cuenta de trabajo, su resumen no debería salir por
tu cuenta personal.

## Seguridad

La página escucha solo en `127.0.0.1` y las acciones exigen un header que un formulario de otro
sitio no puede mandar; solo responde con el `Host` de loopback (corta DNS rebinding). Para verla desde otro dispositivo, ponele adelante un proxy **con
autenticación** que pase al backend `Host: 127.0.0.1:<port>` (el default de nginx con
`proxy_pass http://127.0.0.1:<port>/`): la página puede reanudar y cerrar sesiones en tu máquina.

## Limitaciones

- Solo Claude Code. herdr ya distingue el agente de cada panel; sumar Codex u otro es un
  adaptador (dónde vive el transcript, cómo se reanuda).
- Interfaz y resúmenes en español.
- Aparcar termina el proceso: tareas en segundo plano, subagentes corriendo y el estado de los
  MCP no vuelven.

## Licencia

MIT
