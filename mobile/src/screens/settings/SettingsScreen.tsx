import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Alert,
  Platform,
} from 'react-native';
import {
  TextInput,
  Button,
  List,
  Text,
  HelperText,
} from 'react-native-paper';
import { useNavigation } from '@react-navigation/native';
import { useSettingsStore } from '@stores/settingsStore';
import { API_CONFIG, COLORS } from '@config/constants';

export default function SettingsScreen() {
  const navigation = useNavigation();
  const { apiUrl, setApiUrl, resetToDefaults } = useSettingsStore();

  const [url, setUrl] = useState(apiUrl);
  const [urlError, setUrlError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const validateUrl = (urlString: string): boolean => {
    try {
      new URL(urlString);
      return true;
    } catch {
      return false;
    }
  };

  const handleSave = async () => {
    if (!url.trim()) {
      setUrlError('API URL is required');
      return;
    }

    if (!validateUrl(url)) {
      setUrlError('Please enter a valid URL');
      return;
    }

    setIsSaving(true);
    try {
      await setApiUrl(url);
      Alert.alert(
        'Success',
        'API URL updated. Please restart the app or re-login for changes to take effect.',
        [
          {
            text: 'OK',
            onPress: () => navigation.goBack(),
          },
        ]
      );
    } catch (error) {
      Alert.alert('Error', 'Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    Alert.alert(
      'Reset Settings',
      'Are you sure you want to reset all settings to defaults?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset',
          style: 'destructive',
          onPress: async () => {
            await resetToDefaults();
            setUrl(API_CONFIG.DEFAULT_URL);
            Alert.alert('Success', 'Settings reset to defaults');
          },
        },
      ]
    );
  };

  const getDefaultUrlForPlatform = () => {
    if (Platform.OS === 'ios') {
      return 'http://localhost:8000';
    } else if (Platform.OS === 'android') {
      return 'http://10.0.2.2:8000';
    }
    return 'https://api.cartulary.example.com';
  };

  return (
    <ScrollView style={styles.container}>
      <List.Section>
        <List.Subheader>Server Configuration</List.Subheader>

        <View style={styles.inputContainer}>
          <TextInput
            label="API Server URL"
            value={url}
            onChangeText={(text) => {
              setUrl(text);
              setUrlError('');
            }}
            keyboardType="url"
            autoCapitalize="none"
            autoCorrect={false}
            error={!!urlError}
            disabled={isSaving}
            style={styles.input}
            mode="outlined"
          />
          <HelperText type="error" visible={!!urlError}>
            {urlError}
          </HelperText>
          <HelperText type="info">
            {Platform.OS === 'ios'
              ? 'For localhost, use: http://localhost:8000'
              : Platform.OS === 'android'
              ? 'For emulator localhost, use: http://10.0.2.2:8000'
              : 'Enter your Cartulary server URL'}
          </HelperText>

          <View style={styles.quickActions}>
            <Text variant="bodySmall" style={styles.quickActionsLabel}>
              Quick Actions:
            </Text>
            <View style={styles.quickButtons}>
              <Button
                mode="outlined"
                compact
                onPress={() => setUrl('http://localhost:8000')}
                style={styles.quickButton}
              >
                Localhost
              </Button>
              {Platform.OS === 'android' && (
                <Button
                  mode="outlined"
                  compact
                  onPress={() => setUrl('http://10.0.2.2:8000')}
                  style={styles.quickButton}
                >
                  Emulator
                </Button>
              )}
              <Button
                mode="outlined"
                compact
                onPress={() => setUrl(API_CONFIG.DEFAULT_URL)}
                style={styles.quickButton}
              >
                Default
              </Button>
            </View>
          </View>
        </View>
      </List.Section>

      <List.Section>
        <List.Subheader>Current Configuration</List.Subheader>
        <List.Item
          title="Active API URL"
          description={apiUrl}
          left={(props) => <List.Icon {...props} icon="check-circle" />}
        />
      </List.Section>

      <View style={styles.actions}>
        <Button
          mode="contained"
          onPress={handleSave}
          loading={isSaving}
          disabled={isSaving || url === apiUrl}
          style={styles.button}
        >
          Save Changes
        </Button>

        <Button
          mode="outlined"
          onPress={handleReset}
          disabled={isSaving}
          style={styles.button}
        >
          Reset to Defaults
        </Button>
      </View>

      <View style={styles.info}>
        <Text variant="bodySmall" style={styles.infoText}>
          Note: Changing the API URL requires restarting the app or logging out
          and back in.
        </Text>
        <Text variant="bodySmall" style={styles.infoText}>
          Make sure your Cartulary backend is running and accessible at the
          configured URL.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  inputContainer: {
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  input: {
    marginBottom: 8,
  },
  quickActions: {
    marginTop: 8,
  },
  quickActionsLabel: {
    color: COLORS.textSecondary,
    marginBottom: 8,
  },
  quickButtons: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  quickButton: {
    flex: 0,
  },
  actions: {
    padding: 16,
    gap: 12,
  },
  button: {
    marginVertical: 4,
  },
  info: {
    padding: 16,
    paddingTop: 8,
  },
  infoText: {
    color: COLORS.textSecondary,
    marginBottom: 8,
    lineHeight: 20,
  },
});
