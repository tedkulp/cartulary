# Expo Go Limitations & Solutions

## Current Issue

You're seeing an error because `react-native-pdf` is a **native module** that requires custom native code. Expo Go doesn't include this module, so you have two options:

## ✅ Option 1: Test Without PDF Viewing (Quick - 0 minutes)

The app now gracefully handles this! You can test **everything except PDF viewing**:

✅ **Works in Expo Go:**
- Login/Register with email/password
- OIDC/SSO authentication
- Document list with pagination
- Camera capture and upload
- **Image viewing** (JPG, PNG, etc.)
- Search (full-text and semantic)
- Settings and profile
- **Sharing PDFs** (even if you can't view them)

❌ **Doesn't work in Expo Go:**
- PDF viewing (you'll see a helpful message instead)

### To Test Now:
```bash
# Already running? Great! The app will now work.
# If not:
pnpm start

# Then scan QR code with Expo Go
```

When you try to view a PDF, you'll see a message explaining PDF viewing requires a development build, but you can still share the PDF.

---

## ✅ Option 2: Create Development Build (Full Features - 15 minutes)

For **full PDF support**, create a custom development build:

### Prerequisites
- EAS CLI: `npm install -g eas-cli`
- Expo account: `eas login`

### Build Development Client

#### For iOS Simulator (Mac only)
```bash
# Create development build for iOS simulator
eas build --profile development --platform ios

# When complete, download and install the .tar.gz
# Then run:
pnpm start --dev-client
```

#### For Android Emulator
```bash
# Create development build for Android
eas build --profile development --platform android

# When complete, download the APK and install on emulator
# Then run:
pnpm start --dev-client
```

#### For Physical Device
```bash
# iOS (requires Apple Developer account)
eas build --profile development --platform ios

# Android
eas build --profile development --platform android

# Install the app on your device, then:
pnpm start --dev-client
```

### EAS Configuration

Create `eas.json` in the project root:

```json
{
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "ios": {
        "simulator": true
      }
    },
    "preview": {
      "distribution": "internal"
    },
    "production": {
      "autoIncrement": true
    }
  }
}
```

### After Building

Once you have the development build installed:

1. Install the custom build on your device/simulator
2. Run `pnpm start --dev-client`
3. Open the installed app (not Expo Go)
4. All features including PDF viewing will work!

---

## Comparison

| Feature | Expo Go | Development Build |
|---------|---------|-------------------|
| Setup Time | 0 min | 15-30 min |
| Image Viewing | ✅ | ✅ |
| PDF Viewing | ❌ | ✅ |
| Camera | ✅ | ✅ |
| Search | ✅ | ✅ |
| Auth | ✅ | ✅ |
| Over-the-Air Updates | ✅ | ✅ (with EAS Update) |

---

## Recommendation

### For Quick Testing
Use **Expo Go** (Option 1) - most features work, perfect for initial development

### For Full Features
Create a **Development Build** (Option 2) - takes a bit longer but gives you everything

### For Production
You'll need to create production builds anyway, so creating a development build now gives you experience with the process!

---

## Additional Resources

- [Expo Development Builds](https://docs.expo.dev/development/introduction/)
- [EAS Build](https://docs.expo.dev/build/introduction/)
- [Expo Go Limitations](https://docs.expo.dev/workflow/expo-go/)

---

## Current App Status

✅ **Fixed!** The app now works in Expo Go with graceful degradation for PDF viewing. Upload documents, use camera, search, and manage everything - just view PDFs in another app using the Share button.
