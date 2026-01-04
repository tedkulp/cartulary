# Cartulary Mobile - Quick Start Guide

Get up and running with the Cartulary React Native app in minutes!

## Prerequisites

- Node.js 18+ installed
- pnpm installed (`npm install -g pnpm`)
- Expo Go app on your phone (optional, for quick testing)
- Cartulary backend running (see main project README)

## 5-Minute Setup

### 1. Install Dependencies

```bash
cd mobile
pnpm install
```

### 2. Start the Development Server

```bash
pnpm start
```

### 3. Open on Your Device

**Option A: Use Expo Go (Fastest)**
1. Install Expo Go on your phone ([iOS](https://apps.apple.com/app/expo-go/id982107779) | [Android](https://play.google.com/store/apps/details?id=host.exp.exponent))
2. Scan the QR code shown in terminal
3. App will open in Expo Go

**Option B: Use Simulator/Emulator**
```bash
# iOS (Mac only)
pnpm ios

# Android
pnpm android
```

### 4. Configure Backend URL

1. Open the app
2. It will fail to connect (expected)
3. On login screen, the error should appear
4. Go to Profile tab → Settings
5. Enter your backend URL:
   - **iOS Simulator**: `http://localhost:8000`
   - **Android Emulator**: `http://10.0.2.2:8000`
   - **Physical Device**: `http://<YOUR_LOCAL_IP>:8000`
6. Save and return to login

### 5. Login

Use credentials from your Cartulary backend:
- Email: Your registered email
- Password: Your password

Or use "Sign in with SSO" if OIDC is configured.

## Testing Features

Once logged in:

1. **Documents Tab**
   - View your documents
   - Pull down to refresh
   - Tap document to view
   - Tap sort icon to change order

2. **Camera Tab**
   - Grant camera permission
   - Capture document
   - Or pick from library
   - Upload automatically

3. **Search Tab**
   - Switch between Full-Text and Semantic
   - Type to search
   - Tap result to view document

4. **Profile Tab**
   - View account info
   - Access settings
   - Logout

## Common Issues

### "Cannot connect to server"
- Check backend is running: `curl http://localhost:8000/api/v1/health`
- Verify API URL in Settings
- On Android emulator, use `10.0.2.2` not `localhost`
- On physical device, use your computer's local IP

### "Network request failed"
- Backend must be accessible from your device
- Check firewall settings
- Ensure backend is running on `0.0.0.0` not `127.0.0.1`

### Camera permission denied
- Go to device Settings → Cartulary → Permissions
- Enable Camera and Photos

## Next Steps

- Read full [README.md](./README.md) for detailed documentation
- Explore the codebase structure in `src/`
- Customize theme in `src/config/theme.ts`
- Add your own features!

## Development Tips

```bash
# Clear Metro cache if you have issues
pnpm clean

# Type check
pnpm type-check

# View on web (limited features)
pnpm web
```

## Need Help?

Check the main [README.md](./README.md) for:
- Full feature list
- Detailed setup instructions
- Troubleshooting guide
- Building for production
- API integration details

Happy coding! 🚀
