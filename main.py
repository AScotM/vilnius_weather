#!/usr/bin/env python3

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import requests

KPH_TO_MPS = 1 / 3.6


class FreeWeatherAPI:
    def __init__(self, city: str = "Vilnius", lat: float = 54.6872, lon: float = 25.2797, enable_cache: bool = False):
        self.city = city
        self.latitude = lat
        self.longitude = lon
        self.enable_cache = enable_cache
        
        self.weather_api_key = os.getenv('WEATHERAPI_KEY', 'demo')
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; WeatherApp/1.0)'
        })
        self.timeout = 15
        self.retry_attempts = 2
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def _validate_url(self, url: str) -> bool:
        return url and url.startswith(('http://', 'https://'))

    def _cache_response(self, cache_file: Path, data: Dict[str, Any]) -> None:
        if self.enable_cache:
            try:
                cache_file.write_text(json.dumps(data))
            except (IOError, TypeError):
                pass

    def _load_cached_response(self, cache_file: Path, max_age: int = 3600) -> Optional[Dict[str, Any]]:
        if self.enable_cache and cache_file.exists():
            try:
                file_age = time.time() - cache_file.stat().st_mtime
                if file_age < max_age:
                    return json.loads(cache_file.read_text())
            except (IOError, json.JSONDecodeError):
                pass
        return None

    def _make_request(self, url: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        if not self._validate_url(url):
            return None

        cache_key = None
        if self.enable_cache and params:
            cache_key = hash(frozenset(params.items()))
            cache_file = Path(f"cache_{cache_key}.json")
            cached_data = self._load_cached_response(cache_file)
            if cached_data:
                return cached_data

        for attempt in range(self.retry_attempts):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                
                if self.enable_cache and cache_key:
                    self._cache_response(Path(f"cache_{cache_key}.json"), data)
                
                return data
                
            except requests.exceptions.Timeout:
                if attempt == self.retry_attempts - 1:
                    return None
                time.sleep(1)
            except (requests.exceptions.RequestException, ValueError):
                return None
        
        return None

    def get_open_meteo(self) -> Optional[Dict[str, Any]]:
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,pressure_msl,wind_speed_10m,wind_direction_10m',
                'timezone': 'Europe/Vilnius'
            }
            
            data = self._make_request(url, params)
            if not data or 'current' not in data:
                return None
            
            current = data['current']
            temperature = current.get('temperature_2m')
            if temperature is None:
                return None
            
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
            
            return {
                'temperature': float(temperature),
                'feels_like': float(current.get('apparent_temperature', temperature)),
                'humidity': float(current.get('relative_humidity_2m', 0)),
                'pressure': float(current.get('pressure_msl', 0)),
                'wind_speed': float(current.get('wind_speed_10m', 0)),
                'wind_direction': float(current.get('wind_direction_10m', 0)),
                'description': weather_descriptions.get(weather_code, "Unknown"),
                'source': 'Open-Meteo',
                'city': self.city
            }
            
        except (ValueError, TypeError):
            return None

    def get_weather_api(self) -> Optional[Dict[str, Any]]:
        try:
            url = "http://api.weatherapi.com/v1/current.json"
            params = {
                'key': self.weather_api_key,
                'q': self.city,
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
                'temperature': float(temperature),
                'feels_like': float(current.get('feelslike_c', temperature)),
                'humidity': float(current.get('humidity', 0)),
                'pressure': float(current.get('pressure_mb', 0)),
                'wind_speed': float(current.get('wind_kph', 0)) * KPH_TO_MPS,
                'wind_direction': float(current.get('wind_degree', 0)),
                'description': current.get('condition', {}).get('text', 'Unknown'),
                'source': 'WeatherAPI',
                'city': self.city
            }
            
        except (ValueError, TypeError):
            return None

    def get_wttr_in(self) -> Optional[Dict[str, Any]]:
        try:
            url = f"https://wttr.in/{self.city}"
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
                'wind_speed': float(current.get('windspeedKmph', 0)) * KPH_TO_MPS,
                'wind_direction': int(current.get('winddirDegree', 0)),
                'description': current.get('weatherDesc', [{}])[0].get('value', 'Unknown'),
                'source': 'wttr.in',
                'city': self.city
            }
            
        except (ValueError, TypeError):
            return None

    def get_all_weather_data(self) -> Dict[str, Dict[str, Any]]:
        results = {}
        
        apis = [
            ('Open-Meteo', self.get_open_meteo),
            ('wttr.in', self.get_wttr_in),
            ('WeatherAPI', self.get_weather_api)
        ]
        
        for name, api_func in apis:
            try:
                result = api_func()
                if result and result.get('temperature') is not None:
                    results[name] = result
            except Exception:
                pass
            
            time.sleep(0.5)
        
        return results


def format_weather_report(results: Dict[str, Dict[str, Any]]) -> str:
    if not results:
        return "No weather data could be retrieved from any source.\n"
    
    report = f"{results[next(iter(results))].get('city', 'WEATHER')} REPORT\n"
    report += "=" * 40 + "\n"
    report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for source, data in results.items():
        report += f"{source}:\n"
        report += f"  Temperature: {data['temperature']:.1f}°C\n"
        
        feels_like = data.get('feels_like')
        if feels_like is not None:
            report += f"  Feels like: {feels_like:.1f}°C\n"
        
        report += f"  Conditions: {data['description']}\n"
        
        humidity = data.get('humidity')
        if humidity is not None:
            report += f"  Humidity: {humidity:.0f}%\n"
        
        pressure = data.get('pressure')
        if pressure is not None:
            report += f"  Pressure: {pressure:.0f} hPa\n"
        
        wind_speed = data.get('wind_speed')
        if wind_speed is not None:
            report += f"  Wind: {wind_speed:.1f} m/s\n"
        
        report += "\n"
    
    temps = [data['temperature'] for data in results.values() if data.get('temperature') is not None]
    if temps:
        avg_temp = sum(temps) / len(temps)
        report += f"Average Temperature: {avg_temp:.1f}°C\n"
    
    report += f"Successful sources: {len(results)}\n"
    
    return report


def main():
    print("Fetching weather data from free APIs...")
    print()
    
    city = os.getenv('WEATHER_CITY', 'Vilnius')
    lat = float(os.getenv('WEATHER_LAT', '54.6872'))
    lon = float(os.getenv('WEATHER_LON', '25.2797'))
    enable_cache = os.getenv('ENABLE_CACHE', 'False').lower() == 'true'
    
    weather = FreeWeatherAPI(city=city, lat=lat, lon=lon, enable_cache=enable_cache)
    results = weather.get_all_weather_data()
    
    print(format_weather_report(results))


if __name__ == "__main__":
    main()
