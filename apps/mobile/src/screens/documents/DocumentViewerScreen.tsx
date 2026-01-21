import React, { useEffect, useState } from 'react';
import {
  View,
  StyleSheet,
  Dimensions,
  Alert,
  ActivityIndicator,
  Image,
  ScrollView,
  Platform,
} from 'react-native';
import { Button, Text, IconButton } from 'react-native-paper';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import { useDocumentStore } from '@stores/documentStore';
import { isPDF, isImage } from '@utils/helpers';
import { COLORS } from '@config/constants';
import type { RootStackScreenProps } from '../../types/navigation';

// Conditionally import PDF viewer - only works in development builds, not Expo Go
let Pdf: any = null;
try {
  Pdf = require('react-native-pdf').default;
} catch (e) {
  console.log('PDF viewer not available in Expo Go');
}

const { width: screenWidth, height: screenHeight } = Dimensions.get('window');

export default function DocumentViewerScreen({
  route,
  navigation,
}: RootStackScreenProps<'DocumentViewer'>) {
  const { documentId } = route.params;
  const { currentDocument, fetchDocumentById } = useDocumentStore();
  const [isDownloading, setIsDownloading] = useState(false);
  const [localUri, setLocalUri] = useState<string | null>(null);

  useEffect(() => {
    // Clear previous document's local URI when documentId changes
    setLocalUri(null);
    loadDocument();
  }, [documentId]);

  useEffect(() => {
    // Only process if currentDocument matches the requested documentId
    if (currentDocument && currentDocument.id === documentId) {
      // Show extracted title in navigation if available
      navigation.setOptions({
        title: currentDocument.extracted_title || currentDocument.title
      });
      downloadDocument();
    }
  }, [currentDocument, documentId]);

  const loadDocument = async () => {
    try {
      await fetchDocumentById(documentId);
    } catch (error) {
      Alert.alert('Error', 'Failed to load document');
      navigation.goBack();
    }
  };

  const downloadDocument = async () => {
    if (!currentDocument) return;

    setIsDownloading(true);
    try {
      console.log('Downloading document:', currentDocument.id, currentDocument.title);
      const { documentService } = await import('@services/document.service');
      const uri = await documentService.download(currentDocument);
      console.log('Document downloaded to:', uri);
      setLocalUri(uri);
    } catch (error) {
      console.error('Failed to download document:', error);
      Alert.alert('Error', 'Failed to download document: ' + (error instanceof Error ? error.message : 'Unknown error'));
    } finally {
      setIsDownloading(false);
    }
  };

  const handleShare = async () => {
    if (!localUri) {
      Alert.alert('Error', 'Document not yet downloaded');
      return;
    }

    try {
      const canShare = await Sharing.isAvailableAsync();
      if (canShare) {
        await Sharing.shareAsync(localUri);
      } else {
        Alert.alert('Error', 'Sharing is not available on this device');
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to share document');
    }
  };

  // Show loading if no document, downloading, or if current document doesn't match requested ID
  if (!currentDocument || currentDocument.id !== documentId || isDownloading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>
          {isDownloading ? 'Downloading document...' : 'Loading...'}
        </Text>
      </View>
    );
  }

  const renderContent = () => {
    if (!localUri) {
      return (
        <View style={styles.errorContainer}>
          <Text>Failed to load document</Text>
          <Button mode="contained" onPress={downloadDocument} style={styles.retryButton}>
            Retry
          </Button>
        </View>
      );
    }

    if (isPDF(currentDocument.mime_type)) {
      if (!Pdf) {
        return (
          <View style={styles.errorContainer}>
            <Text variant="headlineSmall" style={styles.expoGoWarning}>
              PDF Viewer Not Available
            </Text>
            <Text variant="bodyMedium" style={styles.expoGoText}>
              PDF viewing requires a development build. You're currently using Expo Go.
            </Text>
            <Text variant="bodySmall" style={styles.expoGoText}>
              You can still share this document using the button below.
            </Text>
            <Button
              mode="outlined"
              onPress={handleShare}
              style={styles.shareButton}
              icon="share-variant"
            >
              Share Document
            </Button>
          </View>
        );
      }
      return (
        <Pdf
          source={{ uri: localUri }}
          style={styles.pdf}
          onError={(error: any) => {
            console.warn('PDF warning/error (may not be critical):', {
              message: error?.message || error,
              document: currentDocument?.title,
              uri: localUri
            });
          }}
          onLoadComplete={(numberOfPages: number) => {
            console.log(`PDF loaded successfully: "${currentDocument?.title}" (${numberOfPages} pages)`);
          }}
          trustAllCerts={false}
        />
      );
    } else if (isImage(currentDocument.mime_type)) {
      return (
        <ScrollView
          contentContainerStyle={styles.imageContainer}
          maximumZoomScale={3}
          minimumZoomScale={1}
        >
          <Image source={{ uri: localUri }} style={styles.image} resizeMode="contain" />
        </ScrollView>
      );
    }

    return (
      <View style={styles.errorContainer}>
        <Text>Unsupported file type</Text>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      {/* Document info header - shows original when there's an extracted title */}
      {currentDocument?.extracted_title &&
       currentDocument.extracted_title !== currentDocument.title && (
        <View style={styles.headerInfo}>
          <View style={styles.headerRow}>
            <Text variant="bodySmall" style={styles.headerLabel}>
              Original Title:
            </Text>
            <Text variant="bodySmall" style={styles.headerFilename} numberOfLines={1}>
              {currentDocument.original_filename}
            </Text>
          </View>

          <View style={styles.headerRow}>
            <Text variant="bodySmall" style={styles.headerLabel}>
              Uploaded:
            </Text>
            <Text variant="bodySmall" style={styles.headerValue}>
              {new Date(currentDocument.created_at).toLocaleDateString()}
            </Text>
          </View>

          {currentDocument.extracted_date && (
            <View style={styles.headerRow}>
              <Text variant="bodySmall" style={styles.headerLabel}>
                Document Date:
              </Text>
              <Text variant="bodySmall" style={styles.headerValue}>
                {(() => {
                  try {
                    // Parse as date-only (YYYY-MM-DD format) with UTC timezone
                    const date = new Date(currentDocument.extracted_date + 'T00:00:00Z');
                    return date.toLocaleDateString(undefined, {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                      timeZone: 'UTC'
                    });
                  } catch {
                    return currentDocument.extracted_date;
                  }
                })()}
              </Text>
            </View>
          )}
        </View>
      )}

      {renderContent()}

      <View style={styles.actions}>
        <IconButton
          icon="share-variant"
          size={24}
          onPress={handleShare}
          style={styles.actionButton}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  headerInfo: {
    backgroundColor: COLORS.surface,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: COLORS.border,
    gap: 8,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerLabel: {
    color: COLORS.textSecondary,
    fontWeight: '500',
    minWidth: 110,
  },
  headerFilename: {
    color: COLORS.text,
    flex: 1,
  },
  headerValue: {
    color: COLORS.text,
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    color: COLORS.textSecondary,
  },
  pdf: {
    flex: 1,
    width: screenWidth,
    height: screenHeight,
  },
  imageContainer: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  image: {
    width: screenWidth,
    height: screenHeight,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  retryButton: {
    marginTop: 16,
  },
  expoGoWarning: {
    textAlign: 'center',
    marginBottom: 16,
    color: COLORS.text,
  },
  expoGoText: {
    textAlign: 'center',
    marginBottom: 12,
    color: COLORS.textSecondary,
  },
  shareButton: {
    marginTop: 24,
  },
  actions: {
    position: 'absolute',
    bottom: 16,
    right: 16,
    flexDirection: 'row',
  },
  actionButton: {
    backgroundColor: COLORS.primary,
  },
});
