import { Platform } from "react-native";

// Provide dynamic fallback for emulators/simulators
const getBaseUrl = () => {
  // Use your computer's local IP address for physical devices
  // 10.0.2.2 is only for Android emulators
  if (Platform.OS === 'android') return "http://192.168.100.8:8000";
  return "http://localhost:8000"; // iOS Simulator
};

export const API_CONFIG = { endpoint: `${getBaseUrl()}/api/search` };

export const fetchBotResponse = async (query) => {
  const response = await fetch(API_CONFIG.endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({ query, top_k: 3, use_llm: true })
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.error || `HTTP ${response.status}`);
  }

  return response.json();
};
