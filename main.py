#!/usr/bin/env python3

import requests
import json
from datetime import datetime
from typing import Optional, Dict, Any

class FreeWeatherAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; WeatherApp/1.0)'
        })

    def get_open_meteo(self) -> Optional[Dict[str, Any]]:
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': 54.6872,
                'longitude': 25.2797,
                'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,pressure_msl,wind_speed_10m,wind_direction_10m',
                'timezone': 'Europe/Vilnius'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            current = data['current']
            weather_code = current['weather_code']
            
            weather_descriptions = {
                0: "Clear sky",
                1: "Mainly clear", 
                2: "Partly cloudy",
                3: "Overcast",
                45: "Fog",
                48: "Fog",
                51: "Light drizzle",
                53: "Moderate drizzle",
                55: "Dense drizzle",
                61: "Slight rain",
                63: "Moderate rain",
                65: "Heavy rain",
                80: "Slight rain showers",
                81: "Moderate rain showers", 
                82: "Violent rain showers",
                95: "Thunderstorm"
            }
            
            return {
                'temperature': current['temperature_2m'],
                'feels_like': current['apparent_temperature'],
                'humidity': current['relative_humidity_2m'],
                'pressure': current.get('pressure_msl'),
                'wind_speed': current['wind_speed_10m'],
                'wind_direction': current['wind_direction_10m'],
                'description': weather_descriptions.get(weather_code, "Unknown"),
                'source': 'Open-Meteo'
            }
            
        except Exception:
            return None

    def get_weather_api(self) -> Optional[Dict[str, Any]]:
        try:
            url = "http://api.weatherapi.com/v1/current.json"
            params = {
                'key': 'demo',
                'q': 'Vilnius',
                'aqi': 'no'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                current = data['current']
                
                return {
                    'temperature': current['temp_c'],
                    'feels_like': current['feelslike_c'],
                    'humidity': current['humidity'],
                    'pressure': current['pressure_mb'],
                    'wind_speed': current['wind_kph'] / 3.6,
                    'wind_direction': current['wind_degree'],
                    'description': current['condition']['text'],
                    'source': 'WeatherAPI'
                }
            return None
            
        except Exception:
            return None

    def get_wttr_in(self) -> Optional[Dict[str, Any]]:
        try:
            url = "https://wttr.in/Vilnius"
            params = {
                'format': 'j1'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            current = data['current_condition'][0]
            
            return {
                'temperature': float(current['temp_C']),
                'feels_like': float(current['FeelsLikeC']),
                'humidity': int(current['humidity']),
                'pressure': int(current['pressure']),
                'wind_speed': float(current['windspeedKmph']) / 3.6,
                'wind_direction': int(current['winddirDegree']),
                'description': current['weatherDesc'][0]['value'],
                'source': 'wttr.in'
            }
            
        except Exception:
            return None

    def get_all_weather_data(self) -> Dict[str, Dict[str, Any]]:
        results = {}
        
        apis = {
            'Open-Meteo': self.get_open_meteo,
            'wttr.in': self.get_wttr_in,
            'WeatherAPI': self.get_weather_api
        }
        
        for name, api_func in apis.items():
            try:
                result = api_func()
                if result:
                    results[name] = result
            except Exception:
                continue
        
        return results

def format_weather_report(results: Dict[str, Dict[str, Any]]) -> str:
    if not results:
        return "No weather data could be retrieved.\n"
    
    report = "VILNIUS WEATHER REPORT\n"
    report += "======================\n"
    report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for source, data in results.items():
        report += f"{source}:\n"
        report += f"  Temperature: {data['temperature']}C\n"
        if data.get('feels_like'):
            report += f"  Feels like: {data['feels_like']}C\n"
        report += f"  Conditions: {data['description']}\n"
        if data.get('humidity'):
            report += f"  Humidity: {data['humidity']}%\n"
        if data.get('pressure'):
            report += f"  Pressure: {data['pressure']} hPa\n"
        if data.get('wind_speed'):
            report += f"  Wind: {data['wind_speed']:.1f} m/s\n"
        report += "\n"
    
    if results:
        temps = [data['temperature'] for data in results.values() if data.get('temperature')]
        if temps:
            avg_temp = sum(temps) / len(temps)
            report += f"Average Temperature: {avg_temp:.1f}C\n"
        report += f"Sources: {len(results)} successful\n"
    
    return report

def main():
    print("Fetching Vilnius weather from free APIs...")
    print()
    
    weather = FreeWeatherAPI()
    results = weather.get_all_weather_data()
    
    print(format_weather_report(results))

if __name__ == "__main__":
    main()
