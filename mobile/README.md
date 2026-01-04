# Cartulary Mobile (React Native)

A modern React Native mobile application for the Cartulary digital archive system. Built with Expo, TypeScript, and React Native Paper, providing a seamless document management experience on iOS and Android.

## Features

### Core Functionality
- **Authentication**
  - Email/password login and registration
  - Enterprise SSO via OIDC/OAuth2
  - Secure token storage with automatic refresh
  - Persistent sessions

- **Document Management**
  - Browse documents with pagination
  - Pull-to-refresh for updates
  - Sort by date, name, or size
  - View PDFs and images
  - Tag management
  - Document metadata

- **Camera Capture**
  - Capture documents with the camera
  - Import from photo library
  - Automatic image optimization
  - Direct upload to server

- **Search**
  - Full-text search for exact matches
  - Semantic search for meaning-based results
  - Search result highlighting
  - Advanced filtering

- **Settings**
  - Runtime API server configuration
  - No rebuild required for server changes
  - Quick presets for common configurations

## Technology Stack

- **Framework**: Expo SDK 54+ with React Native 0.81+
- **Language**: TypeScript 5.9+ (strict mode)
- **UI Library**: React Native Paper 5.x (Material Design 3)
- **Navigation**: React Navigation 7.x
- **State Management**: Zustand 5.x
- **HTTP Client**: Axios with interceptors
- **Storage**:
  - Expo SecureStore (tokens, credentials)
  - AsyncStorage (preferences, cache)
- **Camera**: Expo Camera
- **PDF Viewer**: react-native-pdf
- **Image Processing**: Expo ImageManipulator

## Project Structure

```
mobile/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── common/          # Generic components (Button, Card, etc.)
│   │   ├── documents/       # Document-specific components
│   │   ├── camera/          # Camera-related components
│   │   ├── search/          # Search components
│   │   └── auth/            # Auth components
│   │
│   ├── screens/             # Screen components
│   │   ├── auth/            # Login, Register
│   │   ├── documents/       # DocumentsScreen, DocumentViewerScreen
│   │   ├── camera/          # CameraScreen
│   │   ├── search/          # SearchScreen
│   │   ├── settings/        # SettingsScreen
│   │   └── ProfileScreen.tsx
│   │
│   ├── navigation/          # Navigation configuration
│   │   ├── RootNavigator.tsx    # Main navigator
│   │   ├── AuthNavigator.tsx    # Auth stack
│   │   └── MainNavigator.tsx    # Main app tabs
│   │
│   ├── stores/              # Zustand state management
│   │   ├── authStore.ts     # Authentication state
│   │   ├── documentStore.ts # Documents state
│   │   └── settingsStore.ts # App settings
│   │
│   ├── services/            # API and business logic
│   │   ├── api.ts           # Axios client with interceptors
│   │   ├── auth.service.ts  # Authentication API
│   │   └── document.service.ts  # Document API
│   │
│   ├── types/               # TypeScript type definitions
│   │   ├── api.ts           # API types
│   │   └── navigation.ts    # Navigation types
│   │
│   ├── config/              # App configuration
│   │   ├── constants.ts     # App constants
│   │   └── theme.ts         # React Native Paper theme
│   │
│   ├── utils/               # Utility functions
│   │   ├── storage.ts       # Storage helpers
│   │   └── helpers.ts       # General helpers
│   │
│   └── hooks/               # Custom React hooks (future)
│
├── assets/                  # Static assets
├── app.json                 # Expo configuration
├── babel.config.js          # Babel configuration
├── tsconfig.json            # TypeScript configuration
├── package.json             # Dependencies
└── README.md                # This file
```

## Prerequisites

- **Node.js**: 18.x or higher
- **pnpm**: 8.x or higher (recommended) or npm/yarn
- **Expo CLI**: Latest version (`npm install -g expo-cli`)
- **iOS Development** (Mac only):
  - Xcode 15+
  - iOS Simulator or physical device
- **Android Development**:
  - Android Studio
  - Android SDK (API 34+)
  - Android Emulator or physical device

## Installation

### 1. Clone and Navigate

```bash
cd /path/to/trapper/mobile
```

### 2. Install Dependencies

```bash
pnpm install
# or
npm install
```

### 3. Configure Backend URL

The app needs to connect to your Cartulary backend server. You can configure this in the Settings screen after launching the app, or set it before building:

**For Development:**
- iOS Simulator: `http://localhost:8000`
- Android Emulator: `http://10.0.2.2:8000`
- Physical Device: `http://<YOUR_LOCAL_IP>:8000` (e.g., `http://192.168.1.100:8000`)

**For Production:**
- Configure your production API URL: `https://api.yourdomain.com`

## Running the App

### Development Mode

```bash
# Start Expo development server
pnpm start

# Run on iOS Simulator
pnpm ios

# Run on Android Emulator
pnpm android

# Run on web (limited functionality)
pnpm web
```

### Using Expo Go

1. Install Expo Go on your physical device:
   - iOS: [App Store](https://apps.apple.com/app/expo-go/id982107779)
   - Android: [Play Store](https://play.google.com/store/apps/details?id=host.exp.exponent)

2. Start the development server:
   ```bash
   pnpm start
   ```

3. Scan the QR code with your device camera (iOS) or Expo Go app (Android)

### Network Configuration for Physical Devices

If testing on a physical device on the same network:

1. Find your computer's local IP address:
   ```bash
   # macOS/Linux
   ifconfig | grep "inet "

   # Windows
   ipconfig
   ```

2. Ensure your Cartulary backend is accessible at that IP

3. Update API URL in app Settings to: `http://<YOUR_IP>:8000`

## Building for Production

### Prerequisites for Building

```bash
# Install EAS CLI globally
npm install -g eas-cli

# Login to Expo account
eas login
```

### Configure EAS Build

Create `eas.json` in the project root:

```json
{
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal",
      "ios": {
        "simulator": true
      }
    },
    "production": {
      "autoIncrement": true
    }
  },
  "submit": {
    "production": {}
  }
}
```

### Build Commands

```bash
# Build for iOS (App Store)
eas build --platform ios --profile production

# Build for Android (Google Play)
eas build --platform android --profile production

# Build APK for direct distribution
eas build --platform android --profile preview

# Build for iOS Simulator (testing)
eas build --platform ios --profile preview
```

### Submitting to App Stores

```bash
# Submit to App Store
eas submit --platform ios

# Submit to Google Play
eas submit --platform android
```

## Configuration

### App Configuration (`app.json`)

Key configuration options:

```json
{
  "expo": {
    "name": "Cartulary",
    "slug": "cartulary",
    "version": "1.0.0",
    "scheme": "cartulary",
    "ios": {
      "bundleIdentifier": "com.cartulary.app"
    },
    "android": {
      "package": "com.cartulary.app"
    }
  }
}
```

### Environment Variables

The app uses runtime configuration for API URLs (no rebuild needed). Configure via Settings screen in the app.

## API Integration

### Connecting to Backend

The app connects to the Cartulary FastAPI backend at the configured API URL. Required backend endpoints:

#### Authentication
- `POST /api/v1/auth/login` - Email/password login
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/refresh` - Token refresh
- `GET /api/v1/auth/me` - Current user
- `GET /api/v1/auth/oidc/config` - OIDC configuration
- `POST /api/v1/auth/oidc/token` - OIDC token exchange

#### Documents
- `GET /api/v1/documents` - List documents (with pagination)
- `GET /api/v1/documents/{id}` - Get document by ID
- `POST /api/v1/documents` - Upload document
- `PATCH /api/v1/documents/{id}` - Update document
- `DELETE /api/v1/documents/{id}` - Delete document
- `GET /api/v1/documents/{id}/download` - Download document
- `GET /api/v1/documents/tags` - Get all tags

#### Search
- `GET /api/v1/search` - Full-text search
- `GET /api/v1/search/advanced` - Semantic search

### Authentication Flow

1. User logs in with email/password or OIDC
2. App receives access and refresh tokens
3. Tokens stored securely in Expo SecureStore
4. Access token added to all API requests via Axios interceptor
5. On 401 response, automatic token refresh attempted
6. If refresh fails, user redirected to login

## Troubleshooting

### Common Issues

#### 1. Metro Bundler Cache Issues

```bash
# Clear cache and restart
pnpm start --clear
```

#### 2. Cannot Connect to Backend

- Verify backend is running: `curl http://localhost:8000/api/v1/health`
- Check API URL in Settings matches your backend
- For Android emulator, use `10.0.2.2` instead of `localhost`
- For physical device, use local network IP
- Disable any VPN or firewall blocking connections

#### 3. Camera Not Working

- Ensure camera permissions are granted
- On iOS, check `Info.plist` for camera permission description
- On Android, check `AndroidManifest.xml` for camera permissions

#### 4. PDF Viewer Issues

```bash
# Reinstall dependencies
rm -rf node_modules
pnpm install

# Rebuild
pnpm ios --clean
# or
pnpm android --clean
```

#### 5. TypeScript Errors

```bash
# Check TypeScript configuration
npx tsc --noEmit

# Restart TypeScript server in VS Code
# Command Palette > TypeScript: Restart TS Server
```

## Development

### Adding New Screens

1. Create screen component in `src/screens/`
2. Add route to navigation types in `src/types/navigation.ts`
3. Register screen in appropriate navigator
4. Update navigation calls to use type-safe routes

### Adding New API Endpoints

1. Add types to `src/types/api.ts`
2. Create service method in `src/services/`
3. Add store actions if needed in `src/stores/`
4. Use in components via hooks

### Code Style

- TypeScript strict mode enabled
- ESLint + Prettier recommended
- Follow React Native best practices
- Use functional components with hooks
- Keep components small and focused
- Extract reusable logic to custom hooks

## Performance Optimization

- Use `React.memo` for expensive components
- Implement virtualization for long lists (already done with FlatList)
- Optimize images before upload
- Use pagination for large datasets
- Cache API responses where appropriate
- Lazy load screens with React Navigation

## Security

- Tokens stored in Expo SecureStore (Keychain/Keystore)
- HTTPS required for production
- PKCE flow for OIDC authentication
- Automatic token refresh
- No sensitive data in AsyncStorage
- Validate all user inputs
- Sanitize file names before upload

## Testing

```bash
# Run tests (when implemented)
pnpm test

# Type checking
pnpm type-check

# Linting
pnpm lint
```

## Contributing

1. Create feature branch from `main`
2. Make changes following code style
3. Test on both iOS and Android
4. Submit pull request with description

## License

[Your License Here]

## Support

For issues and questions:
- GitHub Issues: [Your Repo]
- Documentation: [Your Docs]

## Version History

### 1.0.0 (2026-01-02)
- Initial release
- Email/password authentication
- OIDC/SSO support
- Document management (list, view, upload, delete)
- Camera capture
- Full-text and semantic search
- Runtime API configuration

---

Built with ❤️ using Expo and React Native
