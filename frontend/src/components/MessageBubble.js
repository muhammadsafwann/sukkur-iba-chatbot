import React, { useRef, useEffect, useState } from "react";
import { View, Text, Animated, Image, StyleSheet } from "react-native";
import { THEME } from "../theme";

export const MessageBubble = ({ message, index }) => {
  const isUser = message.from === 'user';
  const slideAnim = useRef(new Animated.Value(20)).current;
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const [imageError, setImageError] = useState({ bot: false, user: false });

  useEffect(() => {
    Animated.parallel([
      Animated.timing(slideAnim, { toValue: 0, duration: 300, delay: 0, useNativeDriver: true }),
      Animated.timing(fadeAnim, { toValue: 1, duration: 300, delay: 0, useNativeDriver: true })
    ]).start();
  }, []);

  return (
    <Animated.View style={[styles.messageRow, isUser ? styles.messageRowUser : styles.messageRowBot,
      { opacity: fadeAnim, transform: [{ translateY: slideAnim }] }]}>
      {!isUser && (
        <View style={styles.avatar}>
          {!imageError.bot ? (
            <Image source={require("../../assets/bot.png")} style={styles.avatarImage} resizeMode="contain"
              onError={() => setImageError(prev => ({ ...prev, bot: true }))} />
          ) : <Text style={styles.avatarEmoji}>🤖</Text>}
        </View>
      )}
      <View style={styles.messageContent}>
        <View style={[styles.bubble, isUser ? styles.userBubble : styles.botBubble]}>
          <Text style={[styles.messageText, isUser ? styles.userText : styles.botText]}>
            {message.text}
          </Text>
        </View>
        <Text style={[styles.timestamp, isUser && styles.timestampRight]}>
          {new Date(message.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
        </Text>
      </View>
      {isUser && (
        <View style={styles.avatar}>
          {!imageError.user ? (
            <Image source={require("../../assets/user.png")} style={styles.avatarImage} resizeMode="contain"
              onError={() => setImageError(prev => ({ ...prev, user: true }))} />
          ) : <Text style={styles.avatarEmoji}>👤</Text>}
        </View>
      )}
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  messageRow: { flexDirection: "row", marginBottom: 20, alignItems: "flex-start" },
  messageRowUser: { justifyContent: "flex-end" },
  messageRowBot: { justifyContent: "flex-start" },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: THEME.white,
    justifyContent: "center",
    alignItems: "center",
    padding: 6,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
    elevation: 2
  },
  avatarImage: { width: "100%", height: "100%" },
  avatarEmoji: { fontSize: 18 },
  messageContent: { maxWidth: "75%", marginHorizontal: 10 },
  bubble: {
    paddingVertical: 14,
    paddingHorizontal: 18,
    borderRadius: 18,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1
  },
  userBubble: { backgroundColor: THEME.userBubble, borderBottomRightRadius: 4 },
  botBubble: { backgroundColor: THEME.botBubble, borderBottomLeftRadius: 4 },
  messageText: { fontSize: 15, lineHeight: 22 },
  userText: { color: THEME.white },
  botText: { color: THEME.textPrimary },
  timestamp: { fontSize: 11, color: THEME.textSecondary, marginTop: 6, marginLeft: 4 },
  timestampRight: { textAlign: "right", marginLeft: 0, marginRight: 4 }
});
