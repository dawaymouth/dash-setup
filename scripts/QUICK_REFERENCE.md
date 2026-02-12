# External Dashboard - Quick Reference

## Create & Deploy Dashboard

```bash
# 1. Export data and build
./scripts/build-external.sh

# 2. Deploy
cd external-builds/[organization]-dashboard-[date]
vercel --prod

# 3. Enable password in Vercel dashboard
# Settings → Deployment Protection → Password Protection

# 4. Share URL + password (via separate channels)
```

## Update Existing Dashboard

```bash
# 1. Export new data
./scripts/build-external.sh
# (Select same organization, new date range)

# 2. Redeploy to same project
cd external-builds/[new-package]
vercel --prod
# (Link to existing project when prompted)

# URL and password stay the same ✅
```

## Password Rotation

**Vercel:**
1. Dashboard → Project → Settings → Deployment Protection
2. Update password → Save
3. Notify customer

**Frequency:** Every 3-6 months or when access changes

## Troubleshooting

### Can't connect to database
- Connect to VPN
- Check `backend/.env` credentials

### Build fails
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Data not showing
- Check `dist/data/*.json` files exist
- Verify VITE_STATIC_DATA=true was set
- Check browser console for errors

### Password doesn't work
- Wait 1-2 minutes for propagation
- Try incognito mode
- Verify enabled in Vercel dashboard

## Security Checklist

Before sharing:
- [ ] Correct organization data only
- [ ] No PII/sensitive info
- [ ] Password protection enabled
- [ ] Strong, unique password
- [ ] URL and password shared separately
- [ ] Access documented

## Cost

**Vercel Free Tier:**
- 100GB/month bandwidth
- Unlimited projects  
- Password protection ✅
- Perfect for most use cases

## Support

Full guide: [EXTERNAL_SHARING.md](../EXTERNAL_SHARING.md)
