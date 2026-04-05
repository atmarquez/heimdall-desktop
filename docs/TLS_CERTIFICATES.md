# Heimdall Desktop – TLS Certificates

This repository documents **how to generate TLS certificates** (`cert.pem` and `key.pem`) 
for **Heimdall Desktop**, and **where they must be placed** in a production or development setup.

---

## ❗ Important Notice

TLS certificates are **machine-specific and environment-specific**.

For this reason:
- ❌ **They must NOT be committed to the main Heimdall Desktop repository**
- ❌ They must NOT be shipped inside the application bundle
- ✅ They are generated locally by the user or administrator

---

## 📁 Where to place the certificates

Heimdall Desktop expects TLS files in the following location:

```text
<Heimdall Base Directory>/resources/ssl/
```

Example (portable distribution):

```text
HeimdallDesktop/
├─ HeimdallDesktop.exe
└─ resources/
   └─ ssl/
      ├─ cert.pem
      └─ key.pem
```

Example (source execution):

```text
heimdall-desktop/
├─ main.py
└─ resources/
   └─ ssl/
      ├─ cert.pem
      └─ key.pem
```

---

## 🔐 Generating certificates with OpenSSL (recommended)

### 1. Generate a private key

```bash
openssl genrsa -out key.pem 2048
```

### 2. Generate a self-signed certificate

```bash
openssl req -new -x509 -key key.pem -out cert.pem -days 365
```

Recommended values:
- Common Name (CN): `localhost`
- Organization: `Heimdall Desktop`
- Country / Locale: optional

---

## 🪟 Generating certificates on Windows using PowerShell (no OpenSSL)

On Windows 10 / 11, you can generate a valid local certificate using PowerShell:

```powershell
$cert = New-SelfSignedCertificate     -DnsName "localhost"     -CertStoreLocation "Cert:\CurrentUser\My"

$pwd = ConvertTo-SecureString -String "heimdall" -Force -AsPlainText

Export-PfxCertificate     -Cert $cert     -FilePath cert.pfx     -Password $pwd
```

Then convert to PEM (optional, requires OpenSSL):

```bash
openssl pkcs12 -in cert.pfx -out cert.pem -nodes
```

---

## ✅ File format requirements

- `cert.pem` → X.509 PEM encoded certificate
- `key.pem`  → RSA private key (PEM)

No password-protected keys are recommended for local automation.

---

## ⚙️ Configuration in Heimdall Desktop

In **Configuration → Server → TLS Options**:

- Certificate file: `resources/ssl/cert.pem`
- Private key file: `resources/ssl/key.pem`
- Minimum TLS version: `TLS 1.2`

Paths can be:
- Relative (resolved against application directory)
- Or absolute

---

## ✅ Security recommendations

- Never commit `cert.pem` or `key.pem` to Git
- Add to `.gitignore`:

```gitignore
resources/ssl/*.pem
```

- Use self-signed certificates only for local or internal networks
- Use CA-issued certificates for exposed servers

---

## 📄 License

This documentation is provided under the GNU GPL v3 license.
It applies only to documentation and examples.

---

## 👤 Author

Naidel