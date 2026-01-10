import React, { useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ActivityIndicator, View } from 'react-native';
import { useAuthStore } from '@stores/authStore';
import { useSettingsStore } from '@stores/settingsStore';
import AuthNavigator from './AuthNavigator';
import MainNavigator from './MainNavigator';
import DocumentViewerScreen from '@screens/documents/DocumentViewerScreen';
import DocumentEditScreen from '@screens/documents/DocumentEditScreen';
import SettingsScreen from '@screens/settings/SettingsScreen';
import type { RootStackParamList } from '../types/navigation';

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function RootNavigator() {
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();
  const { loadSettings } = useSettingsStore();

  useEffect(() => {
    // Load settings and check authentication on mount
    const initialize = async () => {
      await loadSettings();
      await checkAuth();
    };

    initialize();
  }, []);

  if (isLoading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {!isAuthenticated ? (
          <Stack.Screen name="Auth" component={AuthNavigator} />
        ) : (
          <>
            <Stack.Screen name="Main" component={MainNavigator} />
            <Stack.Screen
              name="DocumentViewer"
              component={DocumentViewerScreen}
              options={{
                headerShown: true,
                title: 'Document',
                presentation: 'modal',
              }}
            />
            <Stack.Screen
              name="DocumentEdit"
              component={DocumentEditScreen}
              options={{
                headerShown: true,
                title: 'Edit Document',
                presentation: 'modal',
              }}
            />
            <Stack.Screen
              name="Settings"
              component={SettingsScreen}
              options={{
                headerShown: true,
                title: 'Settings',
                presentation: 'modal',
              }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
