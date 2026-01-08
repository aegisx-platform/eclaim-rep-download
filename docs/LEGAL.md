# ⚖️ Legal & Compliance

## ✅ Legal Use of This Software

This software is **LEGAL** when used correctly because:

### 1. Authorized Access
- Hospitals receive legitimate username/password from NHSO
- No hacking or unauthorized system access
- Uses standard HTTP authentication

### 2. Data Access Rights
- Accesses only data the hospital is authorized to view
- No security bypass or data theft
- No access to other hospitals' data

### 3. Legitimate Purpose
- Hospital's own claim management
- HIS reconciliation
- Auditing and reporting

## ⚠️ PDPA Compliance (พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล)

E-Claim data contains **Personal Data** (HN, CID, names, diagnoses)

### Required Compliance Measures

#### 1. Legal Basis for Processing
- Hospital has legal basis (contract, legal obligation)
- Data used for healthcare, management, and reimbursement

#### 2. Security Safeguards
- ✅ Strong database passwords
- ✅ Access limited to authorized personnel
- ✅ VPN or private network only
- ❌ **NEVER expose to public internet**

#### 3. Access Control
- Configure firewall for internal IPs only
- Consider adding authentication (login system)
- Audit all access logs

#### 4. Data Retention & Deletion
- Keep data only as long as necessary (per NHSO regulations)
- Delete when no longer needed
- Encrypt backups

#### 5. No Unauthorized Sharing
- ❌ Do not send data outside hospital
- ❌ Do not share via public cloud storage
- ❌ Do not export patient data for non-medical purposes

## ❌ Prohibited Uses

**DO NOT** use this software for:
- ❌ Selling or sharing patient data with external parties
- ❌ Using data outside intended purpose (marketing, unauthorized research)
- ❌ Disclosing personal data without authorization
- ❌ Deploying on public cloud without security measures

## Disclaimer

```
This software is developed to help hospitals manage e-claim data.

The developer is NOT responsible for:
- Illegal use of the software
- Data breaches or leaks
- PDPA or other legal violations

Users are responsible for:
- Verifying data accuracy
- Complying with PDPA and relevant laws
- Securing patient data
```

## Security Recommendations

### Production Deployment Checklist

- [ ] Change all default passwords
- [ ] Configure firewall to restrict access
- [ ] Use VPN for remote access
- [ ] Enable HTTPS (SSL/TLS)
- [ ] Add authentication for Web UI
- [ ] Encrypt database backups
- [ ] Enable audit logging
- [ ] Monitor logs regularly
- [ ] Update security patches

### Network Security

```bash
# Allow access only from hospital network
ufw allow from 192.168.1.0/24 to any port 5001

# Block all other access
ufw deny 5001
```

### Authentication (Recommended)

Consider adding:
- Login system for Web UI
- OAuth/LDAP integration with hospital systems
- Two-factor authentication (2FA)
- Session timeout
- Role-based access control (RBAC)

### Data Encryption

- **Database**: Use PostgreSQL/MySQL encryption at rest
- **Backups**: Encrypt backup files
- **Connection**: Use SSL/TLS for database connections
- **Credentials**: Never store plain text passwords

---

**[← Back: Database Guide](DATABASE.md)** | **[Next: Troubleshooting →](TROUBLESHOOTING.md)**
