import React, { useRef, useEffect, useState } from "react";
import { View, Text, Animated, Image, StyleSheet } from "react-native";
import { THEME } from "../theme";

export const TypingIndicator = () => {
  const dot1 = useRef(new Animated.Value(0)).current;
  const dot2 = useRef(new Animated.Value(0)).current;
  const dot3 = useRef(new Animated.Value(0)).current;
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    const animate = (dot, delay) => {
      Animated.loop(Animated.sequence([
        Animated.timing(dot, { toValue: 1, duration: 400, delay, useNativeDriver: true }),
        Animated.timing(dot, { toValue: 0, duration: 400, useNativeDriver: true })
      ])).start();
    };
    animate(dot1, 0); animate(dot2, 200); animate(dot3, 400);
  }, []);

  return (
    <View style={styles.typingContainer}>
      <View style={styles.avatar}>
        {!imageError ? (
          <Image source={require("../../assets/bot.png")} style={styles.avatarImage} resizeMode="contain"
            onError={() => setImageError(true)} />
        ) : <Text style={styles.avatarEmoji}>🤖</Text>}
      </View>
      <View style={styles.typingBubble}>
        <Animated.View style={[styles.dot, { opacity: dot1 }]} />
        <Animated.View style={[styles.dot, { opacity: dot2 }]} />
        <Animated.View style={[styles.dot, { opacity: dot3 }]} />
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  typingContainer: { flexDirection: "row", alignItems: "center", paddingHorizontal: 20, paddingBottom: 12 },
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
  typingBubble: {
    flexDirection: "row",
    gap: 6,
    backgroundColor: THEME.botBubble,
    paddingVertical: 14,
    paddingHorizontal: 18,
    borderRadius: 18,
    marginLeft: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1
  },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: THEME.textSecondary }
});
