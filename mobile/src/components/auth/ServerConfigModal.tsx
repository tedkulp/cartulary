import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  Platform,
} from 'react-native';
import {
  Modal,
  Portal,
  TextInput,
  Button,
  Text,
  HelperText,
  IconButton,
} from 'react-native-paper';
import { useSettingsStore } from '@stores/settingsStore';
import { API_CONFIG, COLORS } from '@config/constants';

interface ServerConfigModalProps {
  visible: boolean;
  onDismiss: () => void;
}

export default function ServerConfigModal({ visible, onDismiss }: ServerConfigModalProps) {
  const { apiUrl, setApiUrl } = useSettingsStore();
  const [url, setUrl] = useState('');
  const [urlError, setUrlError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (visible) {
      setUrl(apiUrl || API_CONFIG.DEFAULT_URL);
      setUrlError('');
    }
  }, [visible, apiUrl]);

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
      setUrlError('Server URL is required');
      return;
    }

    if (!validateUrl(url)) {
      setUrlError('Please enter a valid URL (e.g., http://192.168.1.100:8000)');
      return;
    }

    setIsSaving(true);
    try {
      await setApiUrl(url);
      onDismiss();
    } catch (error) {
      setUrlError('Failed to save server URL');
    } finally {
      setIsSaving(false);
    }
  };

  const setQuickUrl = (quickUrl: string) => {
    setUrl(quickUrl);
    setUrlError('');
  };

  return (
    <Portal>
      <Modal
        visible={visible}
        onDismiss={onDismiss}
        contentContainerStyle={styles.modal}
      >
        <View style={styles.header}>
          <Text variant="headlineSmall">Server Configuration</Text>
          <IconButton
            icon="close"
            size={24}
            onPress={onDismiss}
          />
        </View>

        <View style={styles.content}>
          <Text variant="bodyMedium" style={styles.description}>
            Enter the URL of your Cartulary server
          </Text>

          <TextInput
            label="Server URL"
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
            placeholder="http://192.168.1.100:8000"
          />
          <HelperText type="error" visible={!!urlError}>
            {urlError}
          </HelperText>

          <View style={styles.quickActions}>
            <Text variant="labelMedium" style={styles.quickLabel}>
              Quick Presets:
            </Text>
            <View style={styles.quickButtons}>
              <Button
                mode="outlined"
                compact
                onPress={() => setQuickUrl('http://localhost:8000')}
                style={styles.quickButton}
              >
                Localhost
              </Button>
              {Platform.OS === 'android' && (
                <Button
                  mode="outlined"
                  compact
                  onPress={() => setQuickUrl('http://10.0.2.2:8000')}
                  style={styles.quickButton}
                >
                  Emulator
                </Button>
              )}
              <Button
                mode="outlined"
                compact
                onPress={() => setQuickUrl(API_CONFIG.DEFAULT_URL)}
                style={styles.quickButton}
              >
                Default
              </Button>
            </View>
          </View>

          <HelperText type="info">
            {Platform.OS === 'ios'
              ? 'For local testing, use http://localhost:8000'
              : Platform.OS === 'android'
              ? 'For emulator, use http://10.0.2.2:8000'
              : 'Enter your server URL including http:// or https://'}
          </HelperText>

          <Text variant="bodySmall" style={styles.currentUrl}>
            Current: {apiUrl || 'Not set'}
          </Text>
        </View>

        <View style={styles.actions}>
          <Button
            mode="outlined"
            onPress={onDismiss}
            disabled={isSaving}
            style={styles.button}
          >
            Cancel
          </Button>
          <Button
            mode="contained"
            onPress={handleSave}
            loading={isSaving}
            disabled={isSaving || !url.trim()}
            style={styles.button}
          >
            Save
          </Button>
        </View>
      </Modal>
    </Portal>
  );
}

const styles = StyleSheet.create({
  modal: {
    backgroundColor: COLORS.background,
    margin: 20,
    borderRadius: 8,
    maxHeight: '80%',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 8,
  },
  content: {
    paddingHorizontal: 24,
    paddingBottom: 16,
  },
  description: {
    marginBottom: 16,
    color: COLORS.textSecondary,
  },
  input: {
    marginBottom: 8,
  },
  quickActions: {
    marginTop: 16,
    marginBottom: 8,
  },
  quickLabel: {
    marginBottom: 8,
    color: COLORS.textSecondary,
  },
  quickButtons: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  quickButton: {
    marginRight: 0,
  },
  currentUrl: {
    marginTop: 12,
    color: COLORS.textSecondary,
    fontStyle: 'italic',
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
    padding: 24,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  button: {
    minWidth: 100,
  },
});
