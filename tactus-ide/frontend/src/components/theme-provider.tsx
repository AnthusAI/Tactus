import React, { createContext, useContext, useEffect, useState } from 'react';

type Theme = 'light' | 'dark' | 'system';

interface ThemeProviderProps {
  children: React.ReactNode;
  defaultTheme?: Theme;
  storageKey?: string;
}

interface ThemeProviderState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  resolvedTheme: 'light' | 'dark';
}

const ThemeProviderContext = createContext<ThemeProviderState | undefined>(undefined);

export function ThemeProvider({
  children,
  defaultTheme = 'system',
  storageKey = 'tactus-ui-theme',
  ...props
}: ThemeProviderProps) {
  // Always use system preference, ignore localStorage
  const [theme] = useState<Theme>('system');
  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('light');

  useEffect(() => {
    const root = window.document.documentElement;

    // Detect system preference
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';

    console.log('[ThemeProvider] System theme detected:', systemTheme);
    console.log('[ThemeProvider] matchMedia result:', window.matchMedia('(prefers-color-scheme: dark)').matches);

    // Remove dark class first
    root.classList.remove('dark');

    // Only add 'dark' class if system is dark, otherwise use default (light) styles
    if (systemTheme === 'dark') {
      root.classList.add('dark');
      console.log('[ThemeProvider] Added dark class');
    } else {
      console.log('[ThemeProvider] Using light mode (no dark class)');
    }

    setResolvedTheme(systemTheme);
  }, [theme]);

  useEffect(() => {
    // Listen for system theme changes
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const handleChange = (e: MediaQueryListEvent) => {
      const root = window.document.documentElement;
      root.classList.remove('dark');

      const newTheme = e.matches ? 'dark' : 'light';

      // Only add 'dark' class if system is dark
      if (newTheme === 'dark') {
        root.classList.add('dark');
      }

      setResolvedTheme(newTheme);
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [theme]);

  const value = {
    theme,
    setTheme: () => {
      // No-op: theme is always 'system'
    },
    resolvedTheme,
  };

  return (
    <ThemeProviderContext.Provider {...props} value={value}>
      {children}
    </ThemeProviderContext.Provider>
  );
}

export const useTheme = () => {
  const context = useContext(ThemeProviderContext);

  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }

  return context;
};
