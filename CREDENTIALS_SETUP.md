# Redshift Credentials Setup Guide

This guide is for the **team administrator** who needs to set up database access for the team.

## Overview

**Note:** This team uses **Individual User Accounts** - each team member has their own Redshift username and password. Everyone connects to the same host/port/database, but with their own credentials.

Below are instructions for both approaches for reference:

1. **Individual User Accounts** (Your current setup) - Separate account for each team member
2. **Shared Read-Only Account** (Alternative) - One service account everyone uses

## Option 1: Individual User Accounts (Current Setup)

### Why This Approach?

- **Simplest**: One set of credentials to manage
- **Easy rotation**: Update in one place (password manager)
- **Perfect for dashboards**: Read-only access is sufficient
- **Team friendly**: No individual account management needed

### Setup Steps

#### 1. Create Read-Only Redshift User

Connect to your Redshift cluster and run:

```sql
-- Create the dashboard user
CREATE USER dashboard_readonly PASSWORD 'GENERATE-STRONG-PASSWORD-HERE';

-- Grant usage on the schemas
GRANT USAGE ON SCHEMA analytics TO dashboard_readonly;
GRANT USAGE ON SCHEMA interim TO dashboard_readonly;

-- Grant SELECT on all current tables
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO dashboard_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA interim TO dashboard_readonly;

-- Grant SELECT on future tables (recommended)
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO dashboard_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA interim GRANT SELECT ON TABLES TO dashboard_readonly;

-- Verify permissions
SELECT 
    schemaname,
    tablename,
    HAS_TABLE_PRIVILEGE('dashboard_readonly', schemaname||'.'||tablename, 'SELECT') as can_select
FROM pg_tables 
WHERE schemaname IN ('analytics', 'interim')
ORDER BY schemaname, tablename;
```

**Password Generation:**
```bash
# Generate a strong random password
openssl rand -base64 24
```

#### 2. Test the Credentials

```sql
-- Connect as dashboard_readonly user and test
SELECT 1;
SELECT COUNT(*) FROM analytics.intake_documents;
SELECT COUNT(*) FROM interim.suppliers;
```

#### 3. Store in Password Manager

Add to your team's password manager (1Password, LastPass, etc.):

**Title:** AI Intake Dashboard - Redshift Access

**Fields:**
- Host: `your-cluster.region.redshift.amazonaws.com`
- Port: `5439`
- Database: `dev` (or your database name)
- Username: `dashboard_readonly`
- Password: `[generated password]`

**Notes:**
```
Read-only access for AI Intake Dashboard
Schemas: analytics, interim
Created: [date]
```

#### 4. Share with Team

Update `backend/.env.example` with the shared username:

```bash
# Redshift Connection Settings
# Get password from team password manager: "AI Intake Dashboard - Redshift Access"
REDSHIFT_HOST=your-cluster.region.redshift.amazonaws.com
REDSHIFT_PORT=5439
REDSHIFT_DATABASE=dev
REDSHIFT_USER=dashboard_readonly
REDSHIFT_PASSWORD=get_from_password_manager
```

**Communicate to team:**
> "Dashboard credentials are in our password manager under 'AI Intake Dashboard - Redshift Access'. 
> The setup script will prompt you for these during installation."

#### 5. Maintenance

**Password Rotation (recommended annually):**

```sql
-- Change password
ALTER USER dashboard_readonly PASSWORD 'NEW-STRONG-PASSWORD';
```

Then:
1. Update password in password manager
2. Notify team to update their local `.env`:
   ```bash
   # Team members update their .env file
   nano backend/.env
   # Update REDSHIFT_PASSWORD line
   ```

**Revoke Access (if needed):**

```sql
-- Remove all permissions
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA analytics FROM dashboard_readonly;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA interim FROM dashboard_readonly;
REVOKE USAGE ON SCHEMA analytics FROM dashboard_readonly;
REVOKE USAGE ON SCHEMA interim FROM dashboard_readonly;

-- Drop user
DROP USER dashboard_readonly;
```

---

## Option 2: Shared Read-Only Account (Alternative)

### Why This Approach?

- **Audit trail**: Know who ran which queries
- **Granular control**: Different permissions per user
- **Compliance**: Some organizations require individual accounts

### Setup Steps

#### 1. Create User Template

```sql
-- Template for creating individual users
CREATE USER alice_dashboard PASSWORD 'GENERATE-PASSWORD';
GRANT USAGE ON SCHEMA analytics TO alice_dashboard;
GRANT USAGE ON SCHEMA interim TO alice_dashboard;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO alice_dashboard;
GRANT SELECT ON ALL TABLES IN SCHEMA interim TO alice_dashboard;

-- Repeat for each team member
CREATE USER bob_dashboard PASSWORD 'GENERATE-PASSWORD';
-- ... (same grants) ...
```

#### 2. Automate with Script

Create a script to generate users:

```bash
#!/bin/bash
# create_dashboard_user.sh

USERNAME=$1
PASSWORD=$(openssl rand -base64 24)

psql -h your-cluster.region.redshift.amazonaws.com -U admin -d dev << EOF
CREATE USER ${USERNAME}_dashboard PASSWORD '${PASSWORD}';
GRANT USAGE ON SCHEMA analytics TO ${USERNAME}_dashboard;
GRANT USAGE ON SCHEMA interim TO ${USERNAME}_dashboard;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO ${USERNAME}_dashboard;
GRANT SELECT ON ALL TABLES IN SCHEMA interim TO ${USERNAME}_dashboard;
EOF

echo "User: ${USERNAME}_dashboard"
echo "Password: ${PASSWORD}"
echo "Store in password manager for ${USERNAME}"
```

Usage:
```bash
./create_dashboard_user.sh alice
./create_dashboard_user.sh bob
```

#### 3. Distribute Credentials

For each user:
1. Create password manager entry with their specific credentials
2. Grant them access to their entry only
3. They use their individual username/password in `.env`

#### 4. Update .env.example

```bash
# Redshift Connection Settings
# Get YOUR credentials from password manager: "AI Dashboard - [YourName]"
REDSHIFT_HOST=your-cluster.region.redshift.amazonaws.com
REDSHIFT_PORT=5439
REDSHIFT_DATABASE=dev
REDSHIFT_USER=yourname_dashboard
REDSHIFT_PASSWORD=get_from_password_manager
```

#### 5. Maintenance

**Offboarding:**
```sql
-- Remove user access
DROP USER alice_dashboard;
```

**Password Reset:**
```sql
-- Reset password
ALTER USER alice_dashboard PASSWORD 'NEW-PASSWORD';
```

---

## Security Best Practices

### Password Requirements

- Minimum 20 characters
- Include uppercase, lowercase, numbers, special characters
- Use password generator (not dictionary words)
- Store only in password manager (never in code or Slack)

### Access Control

- **Read-only access only**: Dashboard doesn't need write permissions
- **Specific schemas**: Only grant access to needed schemas (analytics, interim)
- **No admin access**: Dashboard should never have elevated privileges

### Monitoring

**Check active connections:**
```sql
SELECT 
    user_name,
    db_name,
    COUNT(*) as connection_count
FROM stv_sessions
WHERE user_name LIKE '%dashboard%'
GROUP BY user_name, db_name;
```

**Review query history:**
```sql
SELECT 
    user_name,
    query,
    start_time,
    end_time
FROM stl_query
WHERE user_name LIKE '%dashboard%'
ORDER BY start_time DESC
LIMIT 100;
```

### Network Security

**VPN requirement:**
- Ensure Redshift is only accessible via VPN
- Redshift security group should not allow public access
- If using individual accounts, consider IP whitelisting

**Connection encryption:**
```bash
# Verify SSL is enabled (in Python)
import redshift_connector
conn = redshift_connector.connect(
    host='...',
    database='...',
    user='...',
    password='...',
    ssl=True,  # Ensure this is True
    sslmode='verify-ca'
)
```

---

## Troubleshooting

### User Cannot Connect

**Check 1: User exists**
```sql
SELECT * FROM pg_user WHERE usename LIKE '%dashboard%';
```

**Check 2: Permissions granted**
```sql
SELECT 
    schemaname,
    tablename,
    HAS_TABLE_PRIVILEGE('dashboard_readonly', schemaname||'.'||tablename, 'SELECT') as can_select
FROM pg_tables 
WHERE schemaname IN ('analytics', 'interim')
LIMIT 5;
```

**Check 3: VPN connected**
- User must be on VPN
- Test: `nc -zv your-cluster.redshift.amazonaws.com 5439`

**Check 4: Correct credentials**
- Verify hostname, port, database name
- Check for typos in username/password
- Ensure no extra spaces in `.env` file

### Permission Denied Errors

```sql
-- Grant missing permissions
GRANT SELECT ON analytics.table_name TO dashboard_readonly;

-- Or re-grant all
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO dashboard_readonly;
```

### Connection Limits

If team is large and hitting connection limits:

```sql
-- Check current connections
SELECT COUNT(*) FROM stv_sessions;

-- Check connection limit
SHOW max_connections;

-- Consider connection pooling or reducing concurrent users
```

---

## Template: Team Communication

### Initial Setup Email

```
Subject: AI Intake Dashboard - Setup Instructions

Hi team,

The AI Intake Dashboard is ready to use! Here's how to get started:

1. Clone the repository: [repository-url]
2. Run: ./setup.sh
3. When prompted for credentials, use:
   - Get them from our password manager: "AI Intake Dashboard - Redshift Access"
4. Connect to VPN and run: ./start.sh

The dashboard will open automatically in your browser.

Full documentation: See TEAM_SETUP.md in the repository

Questions? Ask in #dashboard-support or contact me directly.

Thanks!
```

### Password Rotation Notice

```
Subject: AI Dashboard - Password Update Required

Hi team,

We've rotated the Redshift password for the dashboard (annual security practice).

Action required:
1. Get new password from password manager: "AI Intake Dashboard - Redshift Access"
2. Update your backend/.env file:
   nano backend/.env
   (update REDSHIFT_PASSWORD line)
3. Restart dashboard: ./stop.sh && ./start.sh

This takes 30 seconds. Let me know if you have issues!
```

---

## FAQ

**Q: Should we use shared or individual accounts?**  
A: For a dashboard with <20 users, shared is simpler. For audit requirements or larger teams, use individual.

**Q: How often should we rotate passwords?**  
A: Annually is sufficient for shared read-only accounts. More frequently if required by policy.

**Q: Can we use IAM authentication instead?**  
A: Yes! This is more secure but complex to set up. See [AWS Redshift IAM Authentication](https://docs.aws.amazon.com/redshift/latest/mgmt/generating-user-credentials.html).

**Q: What if someone leaves the team?**  
A: 
- Shared account: No action needed
- Individual account: `DROP USER their_username_dashboard;`

**Q: How do we know if credentials are compromised?**  
A: Monitor query logs for suspicious activity. If concerned, rotate password immediately.

**Q: Can team members see each other's queries?**  
A: No with individual accounts, N/A with shared account (all queries appear from same user).

---

**Last Updated:** 2026-02-05  
**Contact:** [Your contact information]
