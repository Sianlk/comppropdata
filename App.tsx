import React, {useState} from 'react';
import {
  SafeAreaView, StatusBar, StyleSheet, Text, View,
  TouchableOpacity, Alert, ScrollView, Animated,
} from 'react-native';

const PRIMARY = '#96CEB4';

function App(): React.JSX.Element {
  const [ready, setReady] = useState(false);
  const scale = React.useRef(new Animated.Value(1)).current;

  const onPress = () => {
    Animated.sequence([
      Animated.timing(scale, {toValue: 0.95, duration: 100, useNativeDriver: true}),
      Animated.timing(scale, {toValue: 1, duration: 100, useNativeDriver: true}),
    ]).start(() => {
      setReady(true);
      Alert.alert('CompPropData', 'Welcome! App is running successfully.');
    });
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle='light-content' backgroundColor={PRIMARY} />
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.hero}>
          <View style={styles.iconBox}>
            <Text style={styles.iconText}>C</Text>
          </View>
          <Text style={styles.title}>CompPropData</Text>
          <Text style={styles.tagline}>AI Commercial Property Intelligence Platform</Text>
          {ready && <Text style={styles.badge}>READY FOR STORE</Text>}
        </View>
        <View style={styles.actions}>
          <Animated.View style={{transform: [{scale}]}}>
            <TouchableOpacity style={styles.btn} onPress={onPress} activeOpacity={0.9}>
              <Text style={styles.btnText}>Get Started</Text>
            </TouchableOpacity>
          </Animated.View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: PRIMARY},
  scroll: {flexGrow: 1},
  hero: {flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, paddingTop: 64},
  iconBox: {width: 120, height: 120, borderRadius: 28, backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center', justifyContent: 'center', marginBottom: 24},
  iconText: {fontSize: 60, fontWeight: '900', color: 'white'},
  title: {fontSize: 38, fontWeight: '800', color: 'white', marginBottom: 12, textAlign: 'center'},
  tagline: {fontSize: 16, color: 'rgba(255,255,255,0.8)', textAlign: 'center', lineHeight: 24, marginBottom: 16},
  badge: {backgroundColor: 'rgba(255,255,255,0.15)', paddingHorizontal: 16, paddingVertical: 6,
    borderRadius: 20, color: 'white', fontWeight: '700', fontSize: 12, letterSpacing: 1.5},
  actions: {padding: 32},
  btn: {backgroundColor: 'rgba(255,255,255,0.18)', borderRadius: 18, padding: 22,
    alignItems: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.4)'},
  btnText: {color: 'white', fontSize: 18, fontWeight: '700', letterSpacing: 0.5},
});

export default App;
