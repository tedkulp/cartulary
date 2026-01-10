import React from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Alert,
} from 'react-native';
import {
  List,
  Avatar,
  Text,
  Divider,
  Button,
} from 'react-native-paper';
import { useNavigation } from '@react-navigation/native';
import { useAuthStore } from '@stores/authStore';
import { useSettingsStore } from '@stores/settingsStore';
import { APP_INFO, COLORS } from '@config/constants';

export default function ProfileScreen() {
  const navigation = useNavigation<any>();
  const { user, logout } = useAuthStore();
  const { apiUrl } = useSettingsStore();

  const handleLogout = () => {
    Alert.alert('Logout', 'Are you sure you want to logout?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Logout',
        style: 'destructive',
        onPress: async () => {
          await logout();
        },
      },
    ]);
  };

  const getInitials = (name?: string) => {
    if (!name) return '?';
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Avatar.Text
          size={80}
          label={getInitials(user?.full_name || user?.email)}
          style={styles.avatar}
        />
        <Text variant="headlineSmall" style={styles.name}>
          {user?.full_name || 'User'}
        </Text>
        <Text variant="bodyMedium" style={styles.email}>
          {user?.email}
        </Text>
        {user?.roles && user.roles.length > 0 && (
          <Text variant="bodySmall" style={styles.role}>
            Role: {user.roles.map(r => r.name).join(', ')}
          </Text>
        )}
      </View>

      <Divider style={styles.divider} />

      <List.Section>
        <List.Subheader>Server Configuration</List.Subheader>
        <List.Item
          title="API Server"
          description={apiUrl}
          left={(props) => <List.Icon {...props} icon="server" />}
          right={(props) => <List.Icon {...props} icon="chevron-right" />}
          onPress={() => navigation.navigate('Settings')}
        />
      </List.Section>

      <Divider style={styles.divider} />

      <List.Section>
        <List.Subheader>App Information</List.Subheader>
        <List.Item
          title="Version"
          description={APP_INFO.VERSION}
          left={(props) => <List.Icon {...props} icon="information" />}
        />
        <List.Item
          title="Bundle ID"
          description={APP_INFO.BUNDLE_ID}
          left={(props) => <List.Icon {...props} icon="package" />}
        />
      </List.Section>

      <Divider style={styles.divider} />

      <View style={styles.actions}>
        <Button
          mode="outlined"
          onPress={() => navigation.navigate('Settings')}
          style={styles.button}
          icon="cog"
        >
          Settings
        </Button>
        <Button
          mode="contained"
          onPress={handleLogout}
          style={[styles.button, styles.logoutButton]}
          buttonColor={COLORS.error}
          icon="logout"
        >
          Logout
        </Button>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  header: {
    alignItems: 'center',
    padding: 24,
  },
  avatar: {
    backgroundColor: COLORS.primary,
    marginBottom: 16,
  },
  name: {
    fontWeight: '600',
    marginBottom: 4,
  },
  email: {
    color: COLORS.textSecondary,
  },
  role: {
    marginTop: 8,
    color: COLORS.textSecondary,
    fontStyle: 'italic',
  },
  divider: {
    marginVertical: 8,
  },
  actions: {
    padding: 16,
    gap: 12,
  },
  button: {
    marginVertical: 4,
  },
  logoutButton: {
    marginTop: 8,
  },
});
