import React, { useState } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';
import {
  Searchbar,
  SegmentedButtons,
  Card,
  Text,
  Chip,
  ActivityIndicator,
} from 'react-native-paper';
import { useNavigation } from '@react-navigation/native';
import { useDocumentStore } from '@stores/documentStore';
import { formatFileSize, formatRelativeTime, debounce } from '@utils/helpers';
import { COLORS } from '@config/constants';
import type { SearchResult } from '../../types/api';

export default function SearchScreen() {
  const navigation = useNavigation<any>();
  const { searchResults, isSearching, searchQuery, search, clearSearch } = useDocumentStore();

  const [query, setQuery] = useState('');
  const [searchMode, setSearchMode] = useState<'basic' | 'semantic'>('basic');

  const handleSearch = debounce(async (text: string) => {
    if (text.trim().length < 2) {
      clearSearch();
      return;
    }

    try {
      await search(text, searchMode === 'semantic');
    } catch (error) {
      // Error is handled by store
    }
  }, 500);

  const handleQueryChange = (text: string) => {
    setQuery(text);
    handleSearch(text);
  };

  const renderSearchResult = ({ item }: { item: SearchResult }) => (
    <Card
      style={styles.card}
      onPress={() =>
        navigation.navigate('DocumentViewer', { documentId: item.document.id })
      }
    >
      <Card.Content>
        <View style={styles.cardHeader}>
          <Text variant="titleMedium" style={styles.cardTitle} numberOfLines={2}>
            {item.document.extracted_title || item.document.title}
          </Text>
          {searchMode === 'semantic' && (
            <Chip compact style={styles.scoreChip}>
              {Math.round(item.score * 100)}%
            </Chip>
          )}
        </View>

        {item.document.extracted_title && item.document.extracted_title !== item.document.title && (
          <Text variant="bodySmall" style={styles.originalFilename} numberOfLines={1}>
            {item.document.original_filename}
          </Text>
        )}

        {item.highlights && item.highlights.length > 0 && (
          <View style={styles.highlightsContainer}>
            {item.highlights.map((highlight, idx) => (
              <Text
                key={idx}
                variant="bodySmall"
                style={styles.highlight}
                numberOfLines={2}
              >
                ...{highlight}...
              </Text>
            ))}
          </View>
        )}

        <View style={styles.cardMeta}>
          <Text variant="bodySmall" style={styles.metaText}>
            {formatFileSize(item.document.file_size)}
          </Text>
          <Text variant="bodySmall" style={styles.metaText}>
            •
          </Text>
          <Text variant="bodySmall" style={styles.metaText}>
            {formatRelativeTime(item.document.created_at)}
          </Text>
        </View>

        {item.document.tags && item.document.tags.length > 0 && (
          <View style={styles.tagsContainer}>
            {item.document.tags.slice(0, 3).map((tag) => (
              <Chip
                key={tag.id}
                compact
                style={[
                  styles.tag,
                  tag.color && { backgroundColor: tag.color + '30' }
                ]}
              >
                {tag.name}
              </Chip>
            ))}
            {item.document.tags.length > 3 && (
              <Text variant="bodySmall" style={styles.moreText}>
                +{item.document.tags.length - 3} more
              </Text>
            )}
          </View>
        )}
      </Card.Content>
    </Card>
  );

  return (
    <View style={styles.container}>
      <View style={styles.searchContainer}>
        <Searchbar
          placeholder="Search documents..."
          value={query}
          onChangeText={handleQueryChange}
          style={styles.searchbar}
          autoCorrect={false}
          autoCapitalize="none"
        />

        <SegmentedButtons
          value={searchMode}
          onValueChange={(value) => {
            setSearchMode(value as 'basic' | 'semantic');
            if (query.trim().length >= 2) {
              search(query, value === 'semantic');
            }
          }}
          buttons={[
            {
              value: 'basic',
              label: 'Full-Text',
              icon: 'text-search',
            },
            {
              value: 'semantic',
              label: 'Semantic',
              icon: 'brain',
            },
          ]}
          style={styles.segmentedButtons}
        />
      </View>

      {isSearching ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.primary} />
          <Text style={styles.loadingText}>Searching...</Text>
        </View>
      ) : (
        <FlatList
          data={searchResults}
          renderItem={renderSearchResult}
          keyExtractor={(item) => item.document.id}
          ListEmptyComponent={
            query.trim().length >= 2 ? (
              <View style={styles.emptyContainer}>
                <Text variant="bodyLarge" style={styles.emptyText}>
                  No results found
                </Text>
                <Text variant="bodyMedium" style={styles.emptySubtext}>
                  Try different keywords or use semantic search
                </Text>
              </View>
            ) : (
              <View style={styles.emptyContainer}>
                <Text variant="bodyLarge" style={styles.emptyText}>
                  Search your documents
                </Text>
                <Text variant="bodyMedium" style={styles.emptySubtext}>
                  Use full-text search for exact matches or semantic search for
                  meaning-based results
                </Text>
              </View>
            )
          }
          contentContainerStyle={
            searchResults.length === 0 ? styles.emptyList : undefined
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  searchContainer: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  searchbar: {
    marginBottom: 12,
  },
  segmentedButtons: {
    marginBottom: 8,
  },
  card: {
    marginHorizontal: 16,
    marginVertical: 8,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  cardTitle: {
    flex: 1,
    fontWeight: '600',
  },
  originalFilename: {
    color: COLORS.textSecondary,
    fontSize: 12,
    fontStyle: 'italic',
    marginTop: 4,
  },
  scoreChip: {
    marginLeft: 8,
    backgroundColor: COLORS.primaryLight,
  },
  highlightsContainer: {
    marginTop: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: COLORS.primaryLight + '40',
    borderRadius: 4,
  },
  highlight: {
    fontStyle: 'italic',
    color: COLORS.text,
    marginBottom: 4,
  },
  cardMeta: {
    flexDirection: 'row',
    marginTop: 8,
    gap: 8,
  },
  metaText: {
    color: COLORS.textSecondary,
  },
  tagsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 8,
    marginBottom: 4,
    gap: 4,
  },
  tag: {
    marginVertical: 2,
  },
  moreText: {
    marginLeft: 4,
    color: COLORS.textSecondary,
    alignSelf: 'center',
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
});
