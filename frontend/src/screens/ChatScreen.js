import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  ActivityIndicator,
  StatusBar,
  Image,
  Modal,
  Alert,
  RefreshControl,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { SafeAreaView } from "react-native-safe-area-context";
import { THEME } from "../theme";
import { fetchBotResponse } from "../services/api";
import { MessageBubble } from "../components/MessageBubble";
import { TypingIndicator } from "../components/TypingIndicator";

const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
const CONVERSATIONS_KEY = "@all_conversations";

const createWelcomeMessage = () => ({
  id: generateId(),
  from: 'bot',
  text: "Your go‑to guide for Sukkur IBA – ask anything about admissions, fees, scholarships, and life on campus.",
  timestamp: Date.now()
});

export const ChatScreen = () => {
  const [conversations, setConversations] = useState([]);
  const [currentConvId, setCurrentConvId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [isFirstLoad, setIsFirstLoad] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const flatListRef = useRef();
  const scrollEndTimer = useRef(null);

  // FIX: A ref flag that sendMessage sets to true before updating messages.
  // This tells the auto-scroll useEffect to scroll unconditionally — regardless
  // of isNearBottom — because the user themselves just sent a message and must
  // always see it. The flag is reset immediately after each forced scroll so
  // that subsequent bot replies still respect the isNearBottom guard.
  const forceScrollRef = useRef(false);

  const loadAllData = async (isRefresh = false) => {
    try {
      console.log("🔄 loadAllData started");
      const storedConvs = await AsyncStorage.getItem(CONVERSATIONS_KEY);
      console.log("📦 storedConvs:", storedConvs ? "exists" : "null");
      let convs = storedConvs ? JSON.parse(storedConvs) : [];

      console.log(`✅ Loaded ${convs.length} previous conversations`);
      setConversations(convs);

      if (!isRefresh) {
        const newId = generateId();
        setCurrentConvId(newId);
        setMessages([createWelcomeMessage()]);
        console.log(`✨ Started fresh new chat: ${newId}`);
      }
    } catch (error) {
      console.error("❌ Failed to load conversations", error);
      if (!isRefresh) {
        const newId = generateId();
        setConversations([]);
        setCurrentConvId(newId);
        setMessages([createWelcomeMessage()]);
      }
    } finally {
      setIsFirstLoad(false);
      setRefreshing(false);
      console.log("🏁 loadAllData finished");
    }
  };

  const saveConversations = async (newConvs) => {
    try {
      await AsyncStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(newConvs));
      console.log("💾 Saved conversations");
    } catch (error) {
      console.error("❌ Failed to save conversations", error);
    }
  };

  const updateCurrentConversation = (newMessages, titleOverride = null) => {
    setMessages(newMessages);
    setConversations(prevConvs => {
      const existingIndex = prevConvs.findIndex(conv => conv.id === currentConvId);
      let updatedConvs;

      if (existingIndex === -1) {
        const freshConv = {
          id: currentConvId,
          title: titleOverride
            ? (titleOverride.length > 30 ? titleOverride.substring(0, 30) + "..." : titleOverride)
            : "New Chat",
          messages: newMessages,
          updatedAt: Date.now()
        };
        updatedConvs = [freshConv, ...prevConvs];
      } else {
        updatedConvs = prevConvs.map(conv => {
          if (conv.id === currentConvId) {
            const updatedConv = { ...conv, messages: newMessages, updatedAt: Date.now() };
            if (titleOverride && conv.title === "New Chat") {
              updatedConv.title = titleOverride.length > 30
                ? titleOverride.substring(0, 30) + "..."
                : titleOverride;
            }
            return updatedConv;
          }
          return conv;
        });
      }

      updatedConvs.sort((a, b) => b.updatedAt - a.updatedAt);
      saveConversations(updatedConvs);
      return updatedConvs;
    });
  };

  const createNewConversation = () => {
    const newId = generateId();
    setCurrentConvId(newId);
    setMessages([createWelcomeMessage()]);
    setModalVisible(false);
    console.log("✨ Created new conversation:", newId);
  };

  const deleteConversation = (convId) => {
    Alert.alert(
      "Delete Conversation",
      "Are you sure you want to delete this chat?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            setConversations(prevConvs => {
              let newConvs = prevConvs.filter(conv => conv.id !== convId);
              newConvs.sort((a, b) => b.updatedAt - a.updatedAt);
              saveConversations(newConvs);
              return newConvs;
            });

            if (convId === currentConvId) {
              const newId = generateId();
              setCurrentConvId(newId);
              setMessages([createWelcomeMessage()]);
              console.log(`🔄 Current chat deleted, started fresh: ${newId}`);
            }

            if (modalVisible) setModalVisible(false);
            console.log("🗑️ Deleted conversation:", convId);
          }
        }
      ]
    );
  };

  const deleteAllConversations = () => {
    Alert.alert(
      "Delete All Chats",
      "Are you sure you want to delete ALL conversations? This action cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete All",
          style: "destructive",
          onPress: async () => {
            try {
              await AsyncStorage.setItem(CONVERSATIONS_KEY, JSON.stringify([]));
              setConversations([]);
              const newId = generateId();
              setCurrentConvId(newId);
              setMessages([createWelcomeMessage()]);
              setModalVisible(false);
              console.log("🗑️ Deleted all conversations and started fresh chat");
            } catch (error) {
              console.error("❌ Failed to delete all conversations", error);
            }
          }
        }
      ]
    );
  };

  const selectConversation = (convId) => {
    const selected = conversations.find(c => c.id === convId);
    if (selected) {
      setCurrentConvId(convId);
      setMessages(selected.messages);
      setModalVisible(false);
      console.log("🔄 Switched to conversation:", convId);
    }
  };

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    const userMsg = { id: generateId(), from: 'user', text: trimmed, timestamp: Date.now() };
    const newMessages = [...messages, userMsg];

    const isFirstUserMessage = newMessages.filter(m => m.from === 'user').length === 1;
    const titleOverride = isFirstUserMessage ? trimmed : null;

    // FIX: Signal the scroll effect to force-scroll to the bottom for this update.
    // Without this, if the user had scrolled up to read old messages (isNearBottom=false),
    // the useEffect would skip scrolling entirely — leaving the screen stuck at the
    // old position even after the user actively sent a new message.
    forceScrollRef.current = true;

    updateCurrentConversation(newMessages, titleOverride);
    setInput("");
    setLoading(true);
    setIsTyping(true);

    try {
      const data = await fetchBotResponse(trimmed);
      const botText = data.results?.[0]?.answer || "Sorry, I couldn't find an answer to that question.";
      const botMessage = { id: generateId(), from: 'bot', text: botText, timestamp: Date.now() };
      setTimeout(() => {
        const finalMessages = [...newMessages, botMessage];
        updateCurrentConversation(finalMessages);
        setIsTyping(false);
      }, 600);
    } catch (error) {
      const errorMsg = {
        id: generateId(),
        from: 'bot',
        text: `⚠️ Error: ${error.message}\n\nPlease check your connection and try again.`,
        timestamp: Date.now()
      };
      const finalMessages = [...newMessages, errorMsg];
      updateCurrentConversation(finalMessages);
      setIsTyping(false);
    } finally {
      setLoading(false);
    }
  };

  const deleteMessage = (msgId) => {
    Alert.alert(
      "Delete Message",
      "Are you sure you want to delete this message?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            const newMessages = messages.filter(m => m.id !== msgId);
            if (newMessages.length === 0) {
              updateCurrentConversation([createWelcomeMessage()]);
            } else {
              updateCurrentConversation(newMessages);
            }
          }
        }
      ]
    );
  };

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadAllData(true);
  }, []);

  useEffect(() => {
    loadAllData();
  }, []);

  const handleScroll = (event) => {
    const { layoutMeasurement, contentOffset, contentSize } = event.nativeEvent;
    const paddingToBottom = 100;
    const isBottom = layoutMeasurement.height + contentOffset.y >= contentSize.height - paddingToBottom;
    setIsNearBottom(isBottom);
  };

  const handleMomentumScrollEnd = (event) => {
    const { layoutMeasurement, contentOffset, contentSize } = event.nativeEvent;
    const paddingToBottom = 100;
    const isBottom = layoutMeasurement.height + contentOffset.y >= contentSize.height - paddingToBottom;
    setIsNearBottom(isBottom);
  };

  // FIX: Added forceScrollRef.current to the scroll condition.
  // Behaviour after fix:
  //   • User sends a message while scrolled up  → always scrolls to bottom (forceScrollRef=true)
  //   • Bot reply arrives while user is near bottom → scrolls (isNearBottom=true)
  //   • Bot reply arrives while user has scrolled up → does NOT scroll (intended — user is reading)
  // The flag is reset immediately after each forced scroll so it does not affect
  // any subsequent bot-reply updates.
  useEffect(() => {
    if (flatListRef.current && !isFirstLoad) {
      if (isNearBottom || forceScrollRef.current) {
        forceScrollRef.current = false;
        setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
      }
    }
  }, [messages, isTyping, isFirstLoad, isNearBottom]);

  const renderConversationItem = ({ item }) => (
    <TouchableOpacity
      style={[styles.conversationItem, item.id === currentConvId && styles.activeConversation]}
      onPress={() => selectConversation(item.id)}
    >
      <View style={styles.convTextContainer}>
        <Text style={styles.convTitle} numberOfLines={1}>{item.title}</Text>
        <Text style={styles.convDate}>
          {new Date(item.updatedAt).toLocaleDateString()}
        </Text>
      </View>
      <TouchableOpacity onPress={() => deleteConversation(item.id)} style={styles.convDeleteButton}>
        <Image source={require("../../assets/trash.png")} style={styles.convDeleteIcon} />
      </TouchableOpacity>
    </TouchableOpacity>
  );

  const renderMessageItem = ({ item }) => (
    <View style={styles.historyItem}>
      <View style={styles.historyTextContainer}>
        <Text style={styles.historySender}>{item.from === 'user' ? 'You' : 'Bot'}</Text>
        <Text style={styles.historyText} numberOfLines={2}>{item.text}</Text>
        <Text style={styles.historyTime}>
          {new Date(item.timestamp).toLocaleTimeString()}
        </Text>
      </View>
      <TouchableOpacity onPress={() => deleteMessage(item.id)} style={styles.deleteButton}>
        <Image source={require("../../assets/trash.png")} style={styles.deleteIcon} />
      </TouchableOpacity>
    </View>
  );

  const renderMessage = ({ item, index }) => <MessageBubble message={item} index={index} />;

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <StatusBar barStyle="light-content" backgroundColor={THEME.primaryDark} />
      <View style={styles.header}>
        <View style={styles.logoContainer}>
          <Image
            source={require("../../assets/unilogo.png")}
            style={styles.logo}
            resizeMode="cover"
          />
        </View>
        <View style={styles.headerContent}>
          <Text style={styles.headerTitle}>University FAQ Chatbot</Text>
          <View style={styles.statusRow}>
            <View style={styles.onlineDot} />
            <Text style={styles.headerSubtitle}>Online</Text>
          </View>
        </View>
        <View style={styles.headerButtons}>
          <TouchableOpacity onPress={createNewConversation} style={styles.headerButton}>
            <Text style={styles.newChatText}>+ New</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setModalVisible(true)} style={styles.headerButton}>
            <Image source={require("../../assets/chat.png")} style={styles.historyIcon} />
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.chatContainer}>
        <FlatList
          ref={flatListRef}
          data={messages}
          renderItem={renderMessage}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.chatContent}
          showsVerticalScrollIndicator={false}
          onScroll={handleScroll}
          onMomentumScrollEnd={handleMomentumScrollEnd}
          scrollEventThrottle={16}
        />
        {isTyping && <TypingIndicator />}
      </View>

      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}>
        <View style={styles.inputContainer}>
          <View style={styles.inputWrapper}>
            <TextInput
              value={input}
              onChangeText={setInput}
              placeholder="Type your message..."
              placeholderTextColor={THEME.textSecondary}
              style={styles.input}
              multiline
              maxLength={500}
            />
            <TouchableOpacity
              onPress={sendMessage}
              style={[styles.sendButton, (!input.trim() || loading) && styles.sendButtonDisabled]}
              disabled={!input.trim() || loading}
            >
              {loading ? <ActivityIndicator color={THEME.white} size="small" /> : <Text style={styles.sendButtonText}>Send</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>

      {/* Conversations Modal (Sidebar) */}
      <Modal
        animationType="slide"
        transparent={true}
        visible={modalVisible}
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContainer}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Chats</Text>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                {conversations.length > 0 && (
                  <TouchableOpacity
                    onPress={deleteAllConversations}
                    style={{ marginRight: 20 }}
                  >
                    <Text style={{ color: THEME.error, fontSize: 15, fontWeight: '600' }}>Delete All</Text>
                  </TouchableOpacity>
                )}
                <TouchableOpacity onPress={() => setModalVisible(false)}>
                  <Text style={styles.closeButton}>✕</Text>
                </TouchableOpacity>
              </View>
            </View>
            {conversations.length === 0 ? (
              <Text style={styles.emptyHistory}>No conversations yet. Start a new chat!</Text>
            ) : (
              <FlatList
                data={conversations}
                renderItem={renderConversationItem}
                keyExtractor={(item) => item.id}
                style={styles.conversationList}
                refreshControl={
                  <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
                }
              />
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: THEME.background },
  header: {
    backgroundColor: THEME.primaryDark,
    paddingTop: Platform.OS === 'ios' ? 50 : 30,
    paddingBottom: 20,
    paddingHorizontal: 20,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 4
  },
  logoContainer: {
    width: 52,
    height: 52,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.2)",
    borderRadius: 26,
    padding: 2,
    marginRight: 16,
    overflow: "hidden",
  },
  logo: { width: 56, height: 56 },
  headerContent: { flex: 1, alignItems: "flex-start" },
  headerButtons: { flexDirection: "row", alignItems: "center", gap: 12 },
  headerButton: { padding: 8 },
  newChatText: { color: THEME.white, fontSize: 14, fontWeight: "600" },
  historyIcon: { width: 28, height: 28, tintColor: THEME.white },
  headerTitle: { fontSize: 18, fontWeight: "700", color: THEME.white, marginBottom: 2 },
  statusRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  onlineDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: THEME.success },
  headerSubtitle: { fontSize: 12, color: "rgba(255,255,255,0.9)" },
  chatContainer: { flex: 1, backgroundColor: THEME.surface },
  chatContent: { padding: 20, paddingBottom: 16 },
  inputContainer: {
    backgroundColor: THEME.background,
    borderTopWidth: 1,
    borderTopColor: THEME.border,
    paddingVertical: 16,
    paddingHorizontal: 20,
    paddingBottom: Platform.OS === 'ios' ? 30 : 20
  },
  inputWrapper: { flexDirection: "row", alignItems: "flex-end", gap: 12 },
  input: {
    flex: 1,
    minHeight: 48,
    maxHeight: 100,
    paddingHorizontal: 18,
    paddingVertical: 14,
    backgroundColor: THEME.inputBg,
    borderRadius: 24,
    fontSize: 15,
    color: THEME.textPrimary,
    borderWidth: 1,
    borderColor: THEME.border
  },
  sendButton: {
    backgroundColor: THEME.primary,
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 24,
    justifyContent: "center",
    alignItems: "center",
    minWidth: 75,
    height: 48,
    shadowColor: THEME.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 3
  },
  sendButtonDisabled: { opacity: 0.5 },
  sendButtonText: { color: THEME.white, fontSize: 15, fontWeight: "600" },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  modalContainer: {
    backgroundColor: THEME.white,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: "80%",
    padding: 20,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  modalTitle: { fontSize: 20, fontWeight: "bold", color: THEME.textPrimary },
  closeButton: { fontSize: 24, fontWeight: "bold", color: THEME.textSecondary },
  conversationList: { flex: 1 },
  conversationItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: THEME.border,
  },
  activeConversation: {
    backgroundColor: THEME.surface,
  },
  convTextContainer: { flex: 1, marginRight: 12 },
  convTitle: { fontSize: 16, fontWeight: "600", color: THEME.textPrimary },
  convDate: { fontSize: 12, color: THEME.textSecondary, marginTop: 2 },
  convDeleteButton: { padding: 8 },
  convDeleteIcon: { width: 20, height: 20, tintColor: THEME.error },
  historyItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: THEME.border,
  },
  historyTextContainer: { flex: 1, marginRight: 12 },
  historySender: { fontSize: 14, fontWeight: "bold", color: THEME.primary },
  historyText: { fontSize: 14, color: THEME.textPrimary, marginVertical: 2 },
  historyTime: { fontSize: 10, color: THEME.textSecondary },
  deleteButton: { padding: 8 },
  deleteIcon: { width: 24, height: 24, tintColor: THEME.error },
  emptyHistory: {
    textAlign: "center",
    color: THEME.textSecondary,
    marginTop: 40,
    fontSize: 16
  }
});