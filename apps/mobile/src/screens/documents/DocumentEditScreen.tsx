import React, { useEffect, useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import {
  TextInput,
  Button,
  Text,
  ActivityIndicator,
  Chip,
} from 'react-native-paper';
import { useDocumentStore } from '@stores/documentStore';
import { COLORS } from '@config/constants';
import type { RootStackScreenProps } from '../../types/navigation';

export default function DocumentEditScreen({
  route,
  navigation,
}: RootStackScreenProps<'DocumentEdit'>) {
  const { documentId } = route.params;
  const { currentDocument, fetchDocumentById, updateDocument } = useDocumentStore();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  // Form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  useEffect(() => {
    loadDocument();
  }, [documentId]);

  useEffect(() => {
    if (currentDocument) {
      setTitle(currentDocument.extracted_title || currentDocument.title);
      setDescription(currentDocument.description || '');
      setIsLoading(false);
    }
  }, [currentDocument]);

  const loadDocument = async () => {
    try {
      await fetchDocumentById(documentId);
    } catch (error) {
      Alert.alert('Error', 'Failed to load document');
      navigation.goBack();
    }
  };

  const handleSave = async () => {
    if (!title.trim()) {
      Alert.alert('Validation Error', 'Title cannot be empty');
      return;
    }

    setIsSaving(true);
    try {
      await updateDocument(documentId, {
        title: title.trim(),
        description: description.trim() || undefined,
      });

      Alert.alert('Success', 'Document updated successfully', [
        {
          text: 'OK',
          onPress: () => navigation.goBack(),
        },
      ]);
    } catch (error) {
      console.error('Failed to update document:', error);
      Alert.alert(
        'Error',
        'Failed to update document: ' +
          (error instanceof Error ? error.message : 'Unknown error')
      );
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>Loading document...</Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {/* Original filename info */}
        {currentDocument?.extracted_title &&
          currentDocument.extracted_title !== currentDocument.title && (
            <View style={styles.infoSection}>
              <Text variant="bodySmall" style={styles.infoLabel}>
                Original Filename:
              </Text>
              <Text variant="bodySmall" style={styles.infoValue}>
                {currentDocument.original_filename}
              </Text>
            </View>
          )}

        {/* Title field */}
        <View style={styles.fieldSection}>
          <Text variant="labelLarge" style={styles.fieldLabel}>
            Title
          </Text>
          <TextInput
            value={title}
            onChangeText={setTitle}
            mode="outlined"
            style={styles.input}
            placeholder="Enter document title"
            maxLength={500}
          />
        </View>

        {/* Description field */}
        <View style={styles.fieldSection}>
          <Text variant="labelLarge" style={styles.fieldLabel}>
            Description
          </Text>
          <TextInput
            value={description}
            onChangeText={setDescription}
            mode="outlined"
            style={styles.textArea}
            placeholder="Add a description (optional)"
            multiline
            numberOfLines={4}
            maxLength={2000}
          />
        </View>

        {/* Tags section (read-only for now) */}
        {currentDocument?.tags && currentDocument.tags.length > 0 && (
          <View style={styles.fieldSection}>
            <Text variant="labelLarge" style={styles.fieldLabel}>
              Tags
            </Text>
            <View style={styles.tagsContainer}>
              {currentDocument.tags.map((tag) => (
                <Chip
                  key={tag.id}
                  style={[
                    styles.tag,
                    tag.color && {
                      backgroundColor: tag.color + '20',
                      borderColor: tag.color + '60',
                    },
                  ]}
                >
                  {tag.name}
                </Chip>
              ))}
            </View>
            <Text variant="bodySmall" style={styles.helperText}>
              Tag editing coming soon
            </Text>
          </View>
        )}

        {/* Metadata info */}
        <View style={styles.metadataSection}>
          <Text variant="labelMedium" style={styles.metadataTitle}>
            Document Information
          </Text>

          {currentDocument?.extracted_date && (
            <View style={styles.metadataRow}>
              <Text variant="bodySmall" style={styles.metadataLabel}>
                Document Date:
              </Text>
              <Text variant="bodySmall" style={styles.metadataValue}>
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

          <View style={styles.metadataRow}>
            <Text variant="bodySmall" style={styles.metadataLabel}>
              File Size:
            </Text>
            <Text variant="bodySmall" style={styles.metadataValue}>
              {((currentDocument?.file_size || 0) / 1024 / 1024).toFixed(2)} MB
            </Text>
          </View>

          <View style={styles.metadataRow}>
            <Text variant="bodySmall" style={styles.metadataLabel}>
              Uploaded:
            </Text>
            <Text variant="bodySmall" style={styles.metadataValue}>
              {currentDocument?.created_at
                ? new Date(currentDocument.created_at).toLocaleString()
                : 'Unknown'}
            </Text>
          </View>

          {currentDocument?.processing_status && (
            <View style={styles.metadataRow}>
              <Text variant="bodySmall" style={styles.metadataLabel}>
                Status:
              </Text>
              <Text variant="bodySmall" style={styles.metadataValue}>
                {currentDocument.processing_status}
              </Text>
            </View>
          )}
        </View>
      </ScrollView>

      {/* Save button */}
      <View style={styles.footer}>
        <Button
          mode="contained"
          onPress={handleSave}
          loading={isSaving}
          disabled={isSaving}
          style={styles.saveButton}
        >
          Save Changes
        </Button>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
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
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 100,
  },
  infoSection: {
    backgroundColor: COLORS.surface,
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
  },
  infoLabel: {
    color: COLORS.textSecondary,
    fontWeight: '500',
    marginBottom: 4,
  },
  infoValue: {
    color: COLORS.text,
  },
  fieldSection: {
    marginBottom: 24,
  },
  fieldLabel: {
    marginBottom: 8,
    color: COLORS.text,
    fontWeight: '600',
  },
  input: {
    backgroundColor: COLORS.background,
  },
  textArea: {
    backgroundColor: COLORS.background,
    minHeight: 100,
  },
  tagsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tag: {
    marginVertical: 2,
    borderWidth: 1,
    backgroundColor: COLORS.primary + '15',
    borderColor: COLORS.primary + '40',
  },
  helperText: {
    marginTop: 8,
    color: COLORS.textSecondary,
    fontStyle: 'italic',
  },
  metadataSection: {
    backgroundColor: COLORS.surface,
    padding: 16,
    borderRadius: 8,
    marginTop: 8,
  },
  metadataTitle: {
    color: COLORS.text,
    fontWeight: '600',
    marginBottom: 12,
  },
  metadataRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: COLORS.border,
  },
  metadataLabel: {
    color: COLORS.textSecondary,
    fontWeight: '500',
  },
  metadataValue: {
    color: COLORS.text,
    flex: 1,
    textAlign: 'right',
    marginLeft: 16,
  },
  footer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: 16,
    backgroundColor: COLORS.background,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: COLORS.border,
  },
  saveButton: {
    backgroundColor: COLORS.primary,
  },
});
