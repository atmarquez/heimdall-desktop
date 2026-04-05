# Heimdall Desktop – Certificados TLS

Este repositorio documenta **cómo generar certificados TLS** (`cert.pem` y `key.pem`) 
para **Heimdall Desktop**, y **dónde deben colocarse** tanto en entornos de desarrollo como de producción.

---

## ❗ Aviso importante

Los certificados TLS son **específicos de cada máquina y entorno**.

Por este motivo:
- ❌ **NO deben subirse al repositorio principal de Heimdall Desktop**
- ❌ **NO deben incluirse dentro del ejecutable ni del paquete de distribución**
- ✅ Deben generarse **localmente por el usuario o administrador**

---

## 📁 Dónde colocar los certificados

Heimdall Desktop espera los ficheros TLS en la siguiente ubicación:

```text
<Directorio base de Heimdall>/resources/ssl/
```

### Ejemplo (distribución portable)

```text
HeimdallDesktop/
├─ HeimdallDesktop.exe
└─ resources/
   └─ ssl/
      ├─ cert.pem
      └─ key.pem
```

### Ejemplo (ejecución desde código fuente)

```text
heimdall-desktop/
├─ main.py
└─ resources/
   └─ ssl/
      ├─ cert.pem
      └─ key.pem
```

---

## 🔐 Generación de certificados con OpenSSL (recomendado)

### 1. Generar la clave privada

```bash
openssl genrsa -out key.pem 2048
```

### 2. Generar un certificado autofirmado

```bash
openssl req -new -x509 -key key.pem -out cert.pem -days 365
```

Valores recomendados durante el proceso:
- **Common Name (CN)**: `localhost`
- **Organization**: `Heimdall Desktop`
- País / localidad: opcional

---

## 🪟 Generación de certificados en Windows con PowerShell (sin OpenSSL)

En Windows 10 / 11 puedes generar un certificado válido usando PowerShell:

```powershell
$cert = New-SelfSignedCertificate     -DnsName "localhost"     -CertStoreLocation "Cert:\CurrentUser\My"

$pwd = ConvertTo-SecureString -String "heimdall" -Force -AsPlainText

Export-PfxCertificate     -Cert $cert     -FilePath cert.pfx     -Password $pwd
```

Después, si necesitas el formato PEM (requiere OpenSSL):

```bash
openssl pkcs12 -in cert.pfx -out cert.pem -nodes
```

---

## ✅ Requisitos de formato

- `cert.pem` → Certificado X.509 en formato PEM
- `key.pem`  → Clave privada RSA en formato PEM

No se recomienda usar claves protegidas por contraseña para automatización local.

---

## ⚙️ Configuración en Heimdall Desktop

En **Configuración → Servidor → Opciones TLS**:

- Certificado: `resources/ssl/cert.pem`
- Clave privada: `resources/ssl/key.pem`
- Versión mínima TLS: `TLS 1.2`

Las rutas pueden ser:
- Relativas (resueltas respecto al directorio base de la aplicación)
- Absolutas

---

## 🔐 Recomendaciones de seguridad

- Nunca subir `cert.pem` ni `key.pem` a Git
- Añadir a `.gitignore`:

```gitignore
resources/ssl/*.pem
resources/ssl/*.key
```

- Usar certificados autofirmados solo en entornos locales o internos
- Usar certificados emitidos por una CA para servidores expuestos

---

## 📄 Licencia

Esta documentación se distribuye bajo la **GNU General Public License v3 (GPLv3)**.
Aplica únicamente a la documentación y ejemplos incluidos.

---

## 👤 Autor

Naidel