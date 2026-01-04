import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  Alert,
  Platform,
  Image,
  Dimensions,
} from 'react-native';
import { useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import * as ImageManipulator from 'expo-image-manipulator';
import * as Print from 'expo-print';
import * as FileSystem from 'expo-file-system/legacy';
import DocumentScanner from 'react-native-document-scanner-plugin';
import { IconButton, Button, Text, ActivityIndicator } from 'react-native-paper';
import { useNavigation } from '@react-navigation/native';
import { useDocumentStore } from '@stores/documentStore';
import { CAMERA_CONFIG, COLORS } from '@config/constants';

export default function CameraScreen() {
  const navigation = useNavigation<any>();
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const [isProcessing, setIsProcessing] = useState(false);

  const { uploadDocument } = useDocumentStore();

  useEffect(() => {
    if (!cameraPermission?.granted) {
      requestCameraPermission();
    }
  }, []);

  const scanDocument = async () => {
    try {
      setIsProcessing(true);

      // Launch document scanner with edge detection
      const { scannedImages } = await DocumentScanner.scanDocument({
        maxNumDocuments: 5, // Allow scanning multiple pages
        letUserAdjustCrop: true, // Allow manual adjustment of detected edges
        responseType: 'imageFilePath',
      });

      if (scannedImages && scannedImages.length > 0) {
        // The scanner returns processed images with perspective correction
        await convertToPdfAndUpload(scannedImages);
      } else {
        setIsProcessing(false);
      }
    } catch (error: any) {
      setIsProcessing(false);

      // User cancelled - not an error
      if (error.message?.includes('cancel')) {
        return;
      }

      console.error('Document scanner error:', error);
      Alert.alert('Error', 'Failed to scan document');
    }
  };

  const pickImage = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsEditing: true,
        quality: CAMERA_CONFIG.IMAGE_QUALITY,
      });

      if (!result.canceled && result.assets[0]) {
        setIsProcessing(true);
        await convertToPdfAndUpload([result.assets[0].uri]);
      }
    } catch (error) {
      console.error('Image picker error:', error);
      Alert.alert('Error', 'Failed to pick image');
    }
  };

  const convertToPdfAndUpload = async (imageUris: string[]) => {
    try {
      console.log(`Converting ${imageUris.length} image(s) to PDF...`);

      // Get image dimensions for proper scaling in PDF
      const getImageDimensions = (uri: string): Promise<{ width: number; height: number }> => {
        return new Promise((resolve, reject) => {
          Image.getSize(
            uri,
            (width, height) => resolve({ width, height }),
            (error) => reject(error)
          );
        });
      };

      // Build HTML with all images for PDF conversion
      let htmlContent = `
        <!DOCTYPE html>
        <html>
          <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
              * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
              }
              body {
                width: 100%;
                height: 100%;
              }
              .page {
                page-break-after: always;
                width: 100%;
                height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 0;
              }
              .page:last-child {
                page-break-after: auto;
              }
              img {
                max-width: 100%;
                max-height: 100%;
                width: auto;
                height: auto;
                object-fit: contain;
              }
            </style>
          </head>
          <body>
      `;

      // Add each image as a page
      for (const uri of imageUris) {
        // Convert file:// URI to base64 for embedding in HTML
        const base64 = await FileSystem.readAsStringAsync(uri, {
          encoding: FileSystem.EncodingType.Base64,
        });

        htmlContent += `
          <div class="page">
            <img src="data:image/jpeg;base64,${base64}" />
          </div>
        `;
      }

      htmlContent += `
          </body>
        </html>
      `;

      // Generate PDF from HTML
      const { uri: pdfUri } = await Print.printToFileAsync({
        html: htmlContent,
        base64: false,
      });

      console.log('PDF created at:', pdfUri);

      // Upload the PDF
      const fileName = `scan_${Date.now()}.pdf`;

      const document = await uploadDocument({
        uri: pdfUri,
        fileName,
        mimeType: 'application/pdf',
        title: fileName,
      });

      setIsProcessing(false);

      // Navigate to the uploaded document
      const pageText = imageUris.length === 1 ? 'page' : 'pages';
      Alert.alert(
        'Success',
        `Document scanned (${imageUris.length} ${pageText}) and uploaded successfully`,
        [
          {
            text: 'View',
            onPress: () => navigation.navigate('DocumentViewer', { documentId: document.id }),
          },
          {
            text: 'Scan Another',
            onPress: () => scanDocument(),
          },
          {
            text: 'Done',
            onPress: () => navigation.navigate('Documents'),
          },
        ]
      );
    } catch (error: any) {
      setIsProcessing(false);
      console.error('PDF conversion/upload error:', error);
      Alert.alert('Error', error.detail || 'Failed to convert and upload document');
    }
  };

  if (!cameraPermission) {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (!cameraPermission.granted) {
    return (
      <View style={styles.permissionContainer}>
        <IconButton
          icon="file-document-outline"
          size={64}
          iconColor={COLORS.primary}
          style={styles.permissionIcon}
        />
        <Text variant="headlineSmall" style={styles.permissionTitle}>
          Camera Access Required
        </Text>
        <Text variant="bodyLarge" style={styles.permissionText}>
          Cartulary needs camera access to scan and capture documents with edge detection
        </Text>
        <Button
          mode="contained"
          onPress={requestCameraPermission}
          style={styles.permissionButton}
          icon="camera"
        >
          Grant Camera Permission
        </Button>
        <Button mode="text" onPress={() => navigation.navigate('Documents')}>
          Go Back
        </Button>
      </View>
    );
  }

  if (isProcessing) {
    return (
      <View style={styles.processingContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.processingText}>Processing and uploading...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <IconButton
          icon="close"
          iconColor={COLORS.text}
          size={28}
          onPress={() => navigation.navigate('Documents')}
        />
      </View>

      <View style={styles.content}>
        <IconButton
          icon="file-document-outline"
          size={120}
          iconColor={COLORS.primary}
          style={styles.mainIcon}
        />

        <Text variant="headlineMedium" style={styles.title}>
          Scan Document
        </Text>

        <Text variant="bodyLarge" style={styles.subtitle}>
          Scan single or multi-page documents as PDF
        </Text>

        <View style={styles.features}>
          <View style={styles.feature}>
            <IconButton icon="crop-free" size={24} iconColor={COLORS.primary} />
            <Text variant="bodyMedium" style={styles.featureText}>
              Auto Edge Detection
            </Text>
          </View>
          <View style={styles.feature}>
            <IconButton icon="crop-rotate" size={24} iconColor={COLORS.primary} />
            <Text variant="bodyMedium" style={styles.featureText}>
              Perspective Correction
            </Text>
          </View>
          <View style={styles.feature}>
            <IconButton icon="file-pdf-box" size={24} iconColor={COLORS.primary} />
            <Text variant="bodyMedium" style={styles.featureText}>
              Convert to PDF
            </Text>
          </View>
        </View>

        <Button
          mode="contained"
          onPress={scanDocument}
          style={styles.scanButton}
          contentStyle={styles.scanButtonContent}
          icon="camera"
        >
          Scan Document
        </Button>

        <Button
          mode="outlined"
          onPress={pickImage}
          style={styles.pickButton}
          icon="image"
        >
          Choose from Library
        </Button>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'flex-start',
    paddingTop: Platform.OS === 'ios' ? 50 : 20,
    paddingHorizontal: 16,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  mainIcon: {
    marginBottom: 16,
  },
  title: {
    fontWeight: '700',
    color: COLORS.text,
    marginBottom: 12,
    textAlign: 'center',
  },
  subtitle: {
    color: COLORS.textSecondary,
    textAlign: 'center',
    marginBottom: 32,
    paddingHorizontal: 16,
  },
  features: {
    width: '100%',
    marginBottom: 48,
    gap: 16,
  },
  feature: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
  },
  featureText: {
    color: COLORS.text,
    marginLeft: 8,
  },
  scanButton: {
    width: '100%',
    marginBottom: 16,
    backgroundColor: COLORS.primary,
  },
  scanButtonContent: {
    paddingVertical: 8,
  },
  pickButton: {
    width: '100%',
    borderColor: COLORS.primary,
  },
  permissionContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
    backgroundColor: COLORS.background,
  },
  permissionIcon: {
    marginBottom: 16,
  },
  permissionTitle: {
    fontWeight: '700',
    color: COLORS.text,
    marginBottom: 12,
    textAlign: 'center',
  },
  permissionText: {
    textAlign: 'center',
    marginBottom: 32,
    color: COLORS.textSecondary,
  },
  permissionButton: {
    marginBottom: 16,
    backgroundColor: COLORS.primary,
  },
  processingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: COLORS.background,
  },
  processingText: {
    marginTop: 16,
    color: COLORS.textSecondary,
  },
});
