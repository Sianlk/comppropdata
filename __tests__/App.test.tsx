import React from 'react';
import {render, fireEvent, waitFor} from '@testing-library/react-native';
import App from '../App';

jest.useFakeTimers();

describe('CompPropData — Core Tests', () => {
  it('renders without crashing', () => {
    const {toJSON} = render(<App />);
    expect(toJSON()).toBeTruthy();
  });

  it('displays the app title', () => {
    const {getAllByText} = render(<App />);
    expect(getAllByText('CompPropData').length).toBeGreaterThan(0);
  });

  it('displays the tagline', () => {
    const {getByText} = render(<App />);
    expect(getByText('AI Commercial Property Intelligence Platform')).toBeTruthy();
  });

  it('renders the get started button', () => {
    const {getByText} = render(<App />);
    expect(getByText('Get Started')).toBeTruthy();
  });

  it('handles button press and shows store-ready badge', async () => {
    const {getByText, findByText} = render(<App />);
    fireEvent.press(getByText('Get Started'));
    jest.runAllTimers();
    const badge = await findByText('READY FOR STORE');
    expect(badge).toBeTruthy();
  });
});
