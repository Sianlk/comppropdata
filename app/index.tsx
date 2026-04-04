// app/index.tsx — Expo Router entry (root redirect)
// CompProp Data | Commercial property intelligence platform
import { Redirect } from 'expo-router';
import { useAuthStore } from '../src/store/authStore';

export default function Index() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return <Redirect href={isAuthenticated ? '/(tabs)/' : '/(auth)/login'} />;
}
