#!/usr/bin/env python3

import requests
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

class FreeWeatherAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; WeatherApp/1.0)'
        })
        self.timeout = 15
        self.retry_attempts = 2

    def _make_request(self, url: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        for attempt in range(self.retry_attempts):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                if attempt == self.retry_attempts - 1:
                    return None
                time.sleep(1)
            except (requests.exceptions.RequestException, ValueError) as e:
                return None
        return None

    def get_open_meteo(self) -> Optional[Dict[str, Any]]:
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': 54.6872,
                'longitude': 25.2797,
                'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,pressure_msl,wind_speed_10m,wind_direction_10m',
                'timezone': 'Europe/Vilnius'
            }
            
            data = self._make_request(url, params)
            if not data or 'current' not in data:
                return None
            
            current = data['current']
            weather_code = current.get('weather_code')
            
            weather_descriptions = {
                0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                45: "Fog", 48: "Depositing rime fog",
                51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                56: "Light freezing drizzle", 57: "Dense freezing drizzle",
                61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                66: "Light freezing rain", 67: "Heavy freezing rain",
                71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
                77: "Snow grains",
                80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                85: "Slight snow showers", 86: "Heavy snow showers",
                95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
            }
            
            temperature = current.get('temperature_2m')
            if temperature is None:
                return None
                
            return {
                'temperature': temperature,
                'feels_like': current.get('apparent_temperature'),
                'humidity': current.get('relative_humidity_2m'),
                'pressure': current.get('pressure_msl'),
                'wind_speed': current.get('wind_speed_10m'),
                'wind_direction': current.get('wind_direction_10m'),
                'description': weather_descriptions.get(weather_code, "Unknown"),
                'source': 'Open-Meteo'
            }
            
        except Exception as e:
            print(f"Open-Meteo error: {e}")
            return None

    def get_weather_api(self) -> Optional[Dict[str, Any]]:
        try:
            url = "http://api.weatherapi.com/v1/current.json"
            params = {
                'key': 'demo',
                'q': 'Vilnius',
                'aqi': 'no'
            }
            
            data = self._make_request(url, params)
            if not data or 'current' not in data:
                return None
            
            current = data['current']
            temperature = current.get('temp_c')
            if temperature is None:
                return None
                
            return {
                'temperature': temperature,
                'feels_like': current.get('feelslike_c'),
                'humidity': current.get('humidity'),
                'pressure': current.get('pressure_mb'),
                'wind_speed': current.get('wind_kph', 0) / 3.6,
                'wind_direction': current.get('wind_degree'),
                'description': current.get('condition', {}).get('text', 'Unknown'),
                'source': 'WeatherAPI'
            }
            
        except Exception as e:
            print(f"WeatherAPI error: {e}")
            return None

    def get_wttr_in(self) -> Optional[Dict[str, Any]]:
        try:
            url = "https://wttr.in/Vilnius"
            params = {'format': 'j1'}
            
            data = self._make_request(url, params)
            if not data or 'current_condition' not in data or not data['current_condition']:
                return None
            
            current = data['current_condition'][0]
            temp_c = current.get('temp_C')
            if temp_c is None:
                return None
                
            return {
                'temperature': float(temp_c),
                'feels_like': float(current.get('FeelsLikeC', temp_c)),
                'humidity': int(current.get('humidity', 0)),
                'pressure': int(current.get('pressure', 0)),
                'wind_speed': float(current.get('windspeedKmph', 0)) / 3.6,
                'wind_direction': int(current.get('winddirDegree', 0)),
                'description': current.get('weatherDesc', [{}])[0].get('value', 'Unknown'),
                'source': 'wttr.in'
            }
            
        except Exception as e:
            print(f"wttr.in error: {e}")
            return None

    def get_all_weather_data(self) -> Dict[str, Dict[str, Any]]:
        results = {}
        
        apis = [
            ('Open-Meteo', self.get_open_meteo),
            ('wttr.in', self.get_wttr_in),
            ('WeatherAPI', self.get_weather_api)
        ]
        
        for name, api_func in apis:
            result = api_func()
            if result and result.get('temperature') is not None:
                results[name] = result
            else:
                print(f"Failed to get data from {name}")
        
        return results

def format_weather_report(results: Dict[str, Dict[str, Any]]) -> str:
    if not results:
        return "No weather data could be retrieved from any source.\n"
    
    report = "VILNIUS WEATHER REPORT\n"
    report += "======================\n"
    report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for source, data in results.items():
        report += f"{source}:\n"
        report += f"  Temperature: {data['temperature']}°C\n"
        if data.get('feels_like') is not None:
            report += f"  Feels like: {data['feels_like']}°C\n"
        report += f"  Conditions: {data['description']}\n"
        if data.get('humidity') is not None:
            report += f"  Humidity: {data['humidity']}%\n"
        if data.get('pressure') is not None:
            report += f"  Pressure: {data['pressure']} hPa\n"
        if data.get('wind_speed') is not None:
            report += f"  Wind: {data['wind_speed']:.1f} m/s\n"
        report += "\n"
    
    temps = [data['temperature'] for data in results.values() if data.get('temperature') is not None]
    if temps:
        avg_temp = sum(temps) / len(temps)
        report += f"Average Temperature: {avg_temp:.1f}°C\n"
    
    report += f"Successful sources: {len(results)}\n"
    
    return report

def main():
    print("Fetching Vilnius weather from free APIs...")
    print()
    
    weather = FreeWeatherAPI()
    results = weather.get_all_weather_data()
    
    print(format_weather_report(results))

if __name__ == "__main__":
    main()
