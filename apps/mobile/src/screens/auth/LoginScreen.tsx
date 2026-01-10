import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
} from 'react-native';
import {
  TextInput,
  Button,
  Text,
  Divider,
  HelperText,
  IconButton,
  Banner,
} from 'react-native-paper';
import { useAuthStore } from '@stores/authStore';
import { useSettingsStore } from '@stores/settingsStore';
import { isValidEmail } from '@utils/helpers';
import ServerConfigModal from '@components/auth/ServerConfigModal';
import type { AuthStackScreenProps } from '../../types/navigation';
import { COLORS } from '@config/constants';

export default function LoginScreen({ navigation }: AuthStackScreenProps<'Login'>) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [showServerConfig, setShowServerConfig] = useState(false);

  const { login, loginWithOIDC, getOIDCConfig, oidcConfig, isLoading, error, clearError } =
    useAuthStore();
  const { apiUrl } = useSettingsStore();

  useEffect(() => {
    // Only fetch OIDC config if server URL is configured
    if (apiUrl) {
      getOIDCConfig();
    }
  }, [apiUrl]);

  useEffect(() => {
    if (error) {
      Alert.alert('Login Failed', error);
      clearError();
    }
  }, [error]);

  const handleLogin = async () => {
    // Validate
    if (!email || !password) {
      Alert.alert('Error', 'Please enter email and password');
      return;
    }

    if (!isValidEmail(email)) {
      setEmailError('Please enter a valid email');
      return;
    }

    try {
      await login({ email, password });
    } catch (err) {
      // Error is handled by store and displayed via Alert
    }
  };

  const handleOIDCLogin = async () => {
    try {
      await loginWithOIDC();
    } catch (err) {
      // Error is handled by store and displayed via Alert
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.headerContainer}>
          <IconButton
            icon="cog"
            size={24}
            onPress={() => setShowServerConfig(true)}
            style={styles.settingsButton}
          />
        </View>

        <View style={styles.header}>
          <Text variant="displaySmall" style={styles.title}>
            Cartulary
          </Text>
          <Text variant="bodyLarge" style={styles.subtitle}>
            Sign in to continue
          </Text>
          {apiUrl && (
            <Text variant="bodySmall" style={styles.serverUrl}>
              Server: {apiUrl}
            </Text>
          )}
        </View>

        {!apiUrl && (
          <Banner
            visible={true}
            actions={[
              {
                label: 'Configure',
                onPress: () => setShowServerConfig(true),
              },
            ]}
            icon="information"
            style={styles.banner}
          >
            Tap the settings icon to configure your Cartulary server
          </Banner>
        )}

        <View style={styles.form}>
          <TextInput
            label="Email"
            value={email}
            onChangeText={(text) => {
              setEmail(text);
              setEmailError('');
            }}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            error={!!emailError}
            disabled={isLoading}
            style={styles.input}
            mode="outlined"
          />
          <HelperText type="error" visible={!!emailError}>
            {emailError}
          </HelperText>

          <TextInput
            label="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry={!showPassword}
            autoCapitalize="none"
            autoCorrect={false}
            disabled={isLoading}
            style={styles.input}
            mode="outlined"
            right={
              <TextInput.Icon
                icon={showPassword ? 'eye-off' : 'eye'}
                onPress={() => setShowPassword(!showPassword)}
              />
            }
          />

          <Button
            mode="contained"
            onPress={handleLogin}
            loading={isLoading}
            disabled={isLoading}
            style={styles.button}
          >
            Sign In
          </Button>

          {oidcConfig?.enabled && (
            <>
              <View style={styles.dividerContainer}>
                <Divider style={styles.divider} />
                <Text variant="bodySmall" style={styles.dividerText}>
                  OR
                </Text>
                <Divider style={styles.divider} />
              </View>

              <Button
                mode="outlined"
                onPress={handleOIDCLogin}
                loading={isLoading}
                disabled={isLoading}
                style={styles.button}
                icon="shield-account"
              >
                Sign in with SSO
              </Button>
            </>
          )}

          <View style={styles.footer}>
            <Text variant="bodyMedium">Don't have an account? </Text>
            <Button
              mode="text"
              onPress={() => navigation.navigate('Register')}
              disabled={isLoading}
              compact
            >
              Sign Up
            </Button>
          </View>
        </View>
      </ScrollView>

      <ServerConfigModal
        visible={showServerConfig}
        onDismiss={() => setShowServerConfig(false)}
      />
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  headerContainer: {
    alignItems: 'flex-end',
    marginBottom: -40,
  },
  settingsButton: {
    margin: 0,
  },
  header: {
    alignItems: 'center',
    marginBottom: 48,
  },
  title: {
    fontWeight: 'bold',
    color: COLORS.primary,
    marginBottom: 8,
  },
  subtitle: {
    color: COLORS.textSecondary,
  },
  serverUrl: {
    marginTop: 8,
    color: COLORS.textSecondary,
    fontSize: 12,
  },
  banner: {
    marginBottom: 24,
  },
  form: {
    width: '100%',
  },
  input: {
    marginBottom: 8,
  },
  button: {
    marginTop: 16,
  },
  dividerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 24,
  },
  divider: {
    flex: 1,
  },
  dividerText: {
    marginHorizontal: 16,
    color: COLORS.textSecondary,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 24,
  },
});
