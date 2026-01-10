import React, { useEffect, useState, useRef } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  RefreshControl,
  Alert,
  TouchableOpacity,
  Animated,
} from 'react-native';
import {
  FAB,
  Menu,
  IconButton,
  Text,
  ActivityIndicator,
} from 'react-native-paper';
import { Swipeable } from 'react-native-gesture-handler';
import { useDocumentStore } from '@stores/documentStore';
import { useNavigation } from '@react-navigation/native';
import { formatFileSize, formatRelativeTime } from '@utils/helpers';
import { COLORS } from '@config/constants';
import type { Document } from '../../types/api';

export default function DocumentsScreen() {
  const navigation = useNavigation<any>();
  const {
    documents,
    isLoading,
    isRefreshing,
    currentPage,
    totalPages,
    fetchDocuments,
    deleteDocument,
  } = useDocumentStore();

  const [sortMenuVisible, setSortMenuVisible] = useState(false);
  const [sortBy, setSortBy] = useState<'created_at' | 'title' | 'file_size'>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Track currently open swipeable row
  const currentlyOpenSwipeableRef = useRef<Swipeable | null>(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      await fetchDocuments({ page: 1, sort_by: sortBy, sort_order: sortOrder });
    } catch (error) {
      Alert.alert('Error', 'Failed to load documents');
    }
  };

  const handleRefresh = async () => {
    try {
      await fetchDocuments({
        page: 1,
        refresh: true,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
    } catch (error) {
      Alert.alert('Error', 'Failed to refresh documents');
    }
  };

  const handleLoadMore = async () => {
    console.log('handleLoadMore called', { currentPage, totalPages, isLoading });

    if (currentPage < totalPages && !isLoading) {
      try {
        console.log('Loading page:', currentPage + 1);
        await fetchDocuments({
          page: currentPage + 1,
          sort_by: sortBy,
          sort_order: sortOrder,
        });
      } catch (error) {
        console.error('Pagination error:', error);
      }
    } else {
      console.log('Not loading more:', {
        reason: isLoading ? 'already loading' : 'no more pages',
        currentPage,
        totalPages
      });
    }
  };

  const handleSort = (field: typeof sortBy) => {
    setSortMenuVisible(false);
    if (field === sortBy) {
      // Toggle order
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
    fetchDocuments({ page: 1, sort_by: field, sort_order: sortOrder });
  };

  const handleDeleteDocument = (doc: Document) => {
    closeCurrentSwipeable();
    Alert.alert('Delete Document', `Are you sure you want to delete "${doc.title}"?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await deleteDocument(doc.id);
            Alert.alert('Success', 'Document deleted');
          } catch (error) {
            Alert.alert('Error', 'Failed to delete document');
          }
        },
      },
    ]);
  };

  const closeCurrentSwipeable = () => {
    if (currentlyOpenSwipeableRef.current) {
      currentlyOpenSwipeableRef.current.close();
    }
  };

  const handleSwipeableOpen = (swipeable: Swipeable) => {
    if (currentlyOpenSwipeableRef.current && currentlyOpenSwipeableRef.current !== swipeable) {
      currentlyOpenSwipeableRef.current.close();
    }
    currentlyOpenSwipeableRef.current = swipeable;
  };

  const handleEditDocument = (doc: Document) => {
    closeCurrentSwipeable();
    navigation.navigate('DocumentEdit', { documentId: doc.id });
  };

  const renderRightActions = (
    progress: Animated.AnimatedInterpolation<number>,
    dragX: Animated.AnimatedInterpolation<number>,
    item: Document
  ) => {
    const trans = dragX.interpolate({
      inputRange: [-160, 0],
      outputRange: [0, 160],
      extrapolate: 'clamp',
    });

    return (
      <Animated.View
        style={[
          styles.swipeActionsContainer,
          { transform: [{ translateX: trans }] },
        ]}
      >
        <TouchableOpacity
          style={[styles.swipeAction, styles.editAction]}
          onPress={() => handleEditDocument(item)}
        >
          <IconButton
            icon="pencil"
            size={24}
            iconColor="#fff"
            style={styles.swipeActionIcon}
          />
          <Text style={styles.swipeActionText}>Edit</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.swipeAction, styles.deleteAction]}
          onPress={() => handleDeleteDocument(item)}
        >
          <IconButton
            icon="trash-can"
            size={24}
            iconColor="#fff"
            style={styles.swipeActionIcon}
          />
          <Text style={styles.swipeActionText}>Delete</Text>
        </TouchableOpacity>
      </Animated.View>
    );
  };

  const renderDocument = ({ item }: { item: Document }) => {
    let swipeableRef: Swipeable | null = null;

    return (
      <Swipeable
        ref={(ref) => (swipeableRef = ref)}
        renderRightActions={(progress, dragX) => renderRightActions(progress, dragX, item)}
        overshootRight={false}
        friction={2}
        onSwipeableOpen={() => swipeableRef && handleSwipeableOpen(swipeableRef)}
      >
        <View style={styles.swipeableContent}>
          <TouchableOpacity
            style={styles.listItem}
            onPress={() => {
              closeCurrentSwipeable();
              navigation.navigate('DocumentViewer', { documentId: item.id });
            }}
            activeOpacity={0.7}
          >
          <View style={styles.itemLeft}>
            {/* File type icon */}
            <View style={[styles.iconContainer, item.processing_status === 'failed' && styles.iconContainerError]}>
              <IconButton
                icon={item.mime_type.includes('pdf') ? 'file-pdf-box' : 'image'}
                size={24}
                iconColor={item.processing_status === 'failed' ? COLORS.error : COLORS.primary}
                style={styles.fileIcon}
              />
            </View>

            {/* Document info */}
            <View style={styles.itemInfo}>
              <Text variant="bodyLarge" style={styles.itemTitle} numberOfLines={2}>
                {item.extracted_title || item.title}
              </Text>
              {item.extracted_title && item.extracted_title !== item.title && (
                <Text variant="bodySmall" style={styles.originalFilename} numberOfLines={1}>
                  {item.original_filename}
                </Text>
              )}

              <View style={styles.itemMeta}>
                <Text variant="bodySmall" style={styles.metaText}>
                  {formatFileSize(item.file_size)}
                </Text>
                <Text variant="bodySmall" style={styles.metaText}> • </Text>
                <Text variant="bodySmall" style={styles.metaText}>
                  {formatRelativeTime(item.created_at)}
                </Text>
              </View>

              <View style={styles.tagsRow}>
                {/* Status tag */}
                {item.processing_status !== 'completed' && (
                  <View
                    style={[
                      styles.statusTag,
                      item.processing_status === 'pending' && styles.statusPending,
                      item.processing_status === 'processing' && styles.statusProcessing,
                      item.processing_status === 'failed' && styles.statusFailed,
                    ]}
                  >
                    <Text variant="bodySmall" style={styles.statusTagText}>
                      {item.processing_status}
                    </Text>
                  </View>
                )}

                {/* Regular tags */}
                {item.tags && item.tags.length > 0 && (
                  <>
                    {item.tags.slice(0, 3).map((tag) => (
                      <View
                        key={tag.id}
                        style={[
                          styles.tag,
                          tag.color && { backgroundColor: tag.color + '20', borderColor: tag.color + '60' }
                        ]}
                      >
                        <Text variant="bodySmall" style={styles.tagText}>
                          {tag.name}
                        </Text>
                      </View>
                    ))}
                    {item.tags.length > 3 && (
                      <Text variant="bodySmall" style={styles.moreText}>
                        +{item.tags.length - 3}
                      </Text>
                    )}
                  </>
                )}
              </View>
            </View>
          </View>

          <IconButton
            icon="chevron-right"
            size={20}
            iconColor={COLORS.textSecondary}
            style={styles.chevron}
          />
        </TouchableOpacity>
        <View style={styles.separator} />
      </View>
    </Swipeable>
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Menu
          visible={sortMenuVisible}
          onDismiss={() => setSortMenuVisible(false)}
          anchor={
            <IconButton
              icon="sort"
              onPress={() => setSortMenuVisible(true)}
            />
          }
        >
          <Menu.Item
            onPress={() => handleSort('created_at')}
            title="Date"
            leadingIcon={sortBy === 'created_at' ? 'check' : undefined}
          />
          <Menu.Item
            onPress={() => handleSort('title')}
            title="Name"
            leadingIcon={sortBy === 'title' ? 'check' : undefined}
          />
          <Menu.Item
            onPress={() => handleSort('file_size')}
            title="Size"
            leadingIcon={sortBy === 'file_size' ? 'check' : undefined}
          />
        </Menu>
      </View>

      <FlatList
        data={documents || []}
        renderItem={renderDocument}
        keyExtractor={(item) => item.id}
        refreshControl={
          <RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} />
        }
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.3}
        onScrollBeginDrag={closeCurrentSwipeable}
        ListEmptyComponent={
          !isLoading ? (
            <View style={styles.emptyContainer}>
              <Text variant="bodyLarge" style={styles.emptyText}>
                No documents yet
              </Text>
              <Text variant="bodyMedium" style={styles.emptySubtext}>
                Tap the camera button to capture your first document
              </Text>
            </View>
          ) : null
        }
        ListFooterComponent={
          isLoading && !isRefreshing ? (
            <View style={styles.loaderContainer}>
              <ActivityIndicator size="small" color={COLORS.primary} />
              <Text style={styles.loadingText}>Loading more...</Text>
            </View>
          ) : null
        }
        contentContainerStyle={(documents || []).length === 0 ? styles.emptyList : undefined}
      />

      <FAB
        icon="camera"
        style={styles.fab}
        onPress={() => navigation.navigate('Camera')}
      />
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
    justifyContent: 'flex-end',
    alignItems: 'center',
    paddingHorizontal: 4,
    paddingTop: 8,
    paddingBottom: 4,
    backgroundColor: COLORS.background,
  },
  swipeableContent: {
    backgroundColor: COLORS.background,
  },
  listItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.background,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  itemLeft: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: COLORS.primary + '10',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  iconContainerError: {
    backgroundColor: COLORS.error + '10',
  },
  fileIcon: {
    margin: 0,
  },
  itemInfo: {
    flex: 1,
  },
  itemTitle: {
    fontWeight: '600',
    color: COLORS.text,
    marginBottom: 2,
  },
  originalFilename: {
    color: COLORS.textSecondary,
    fontSize: 12,
    fontStyle: 'italic',
    marginBottom: 4,
  },
  itemMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  metaText: {
    color: COLORS.textSecondary,
    fontSize: 13,
  },
  tagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 2,
  },
  statusTag: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    borderWidth: 1,
  },
  statusPending: {
    backgroundColor: COLORS.warning + '20',
    borderColor: COLORS.warning + '60',
  },
  statusProcessing: {
    backgroundColor: COLORS.primary + '20',
    borderColor: COLORS.primary + '60',
  },
  statusFailed: {
    backgroundColor: COLORS.error + '20',
    borderColor: COLORS.error + '60',
  },
  statusTagText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.text,
  },
  tag: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    backgroundColor: COLORS.primary + '15',
    borderWidth: 1,
    borderColor: COLORS.primary + '40',
  },
  tagText: {
    fontSize: 12,
    color: COLORS.text,
  },
  moreText: {
    color: COLORS.textSecondary,
    alignSelf: 'center',
    fontSize: 12,
  },
  chevron: {
    margin: 0,
    marginLeft: 8,
  },
  separator: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: COLORS.border,
    marginLeft: 76, // Align with text (icon width + margin)
  },
  swipeActionsContainer: {
    flexDirection: 'row',
    alignItems: 'stretch',
  },
  swipeAction: {
    width: 80,
    justifyContent: 'center',
    alignItems: 'center',
  },
  editAction: {
    backgroundColor: COLORS.primary,
  },
  deleteAction: {
    backgroundColor: COLORS.error,
  },
  swipeActionIcon: {
    margin: 0,
  },
  swipeActionText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
    marginTop: -8,
  },
  emptyList: {
    flexGrow: 1,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  emptyText: {
    color: COLORS.textSecondary,
    marginBottom: 8,
  },
  emptySubtext: {
    color: COLORS.textSecondary,
    textAlign: 'center',
  },
  loaderContainer: {
    paddingVertical: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingText: {
    marginTop: 8,
    color: COLORS.textSecondary,
    fontSize: 13,
  },
  fab: {
    position: 'absolute',
    right: 16,
    bottom: 16,
    backgroundColor: COLORS.primary,
  },
});
