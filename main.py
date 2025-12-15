#!/usr/bin/env python3

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, TypedDict, List
from urllib.parse import quote
import requests

KPH_TO_MPS = 1 / 3.6


class WeatherData(TypedDict):
    temperature: float
    feels_like: float
    humidity: float
    pressure: float
    wind_speed: float
    wind_direction: float
    description: str
    source: str
    city: str


class WeatherAPIConfig:
    def __init__(self):
        self.timeout = 15
        self.retry_attempts = 2
        self.cache_ttl = 3600
        self.request_delay = 0.5
        self.max_cache_age_days = 7


class FreeWeatherAPI:
    def __init__(self, city: str = "Vilnius", lat: float = 54.6872, lon: float = 25.2797, enable_cache: bool = False):
        self.city = city
        self.latitude = lat
        self.longitude = lon
        self.enable_cache = enable_cache
        
        self.config = WeatherAPIConfig()
        self.weather_api_key = os.getenv('WEATHERAPI_KEY', 'demo')
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; WeatherApp/1.0)'
        })
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.open_meteo_weather_codes = {
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
        
        if self.enable_cache:
            self._clean_old_cache()

    def _validate_url(self, url: str) -> bool:
        return bool(url and url.startswith(('http://', 'https://')))

    def _clean_old_cache(self) -> None:
        cache_dir = Path('.')
        cutoff_time = time.time() - (self.config.max_cache_age_days * 86400)
        
        for cache_file in cache_dir.glob('cache_*.json'):
            try:
                if cache_file.stat().st_mtime < cutoff_time:
                    cache_file.unlink()
                    self.logger.debug(f"Removed old cache file: {cache_file}")
            except OSError as e:
                self.logger.warning(f"Failed to remove cache file {cache_file}: {e}")

    def _get_cache_key(self, url: str, params: Dict[str, Any]) -> str:
        if not params:
            return f"cache_{quote(url, safe='')}.json"
        
        sorted_params = sorted(params.items())
        param_hash = hash(frozenset(sorted_params))
        return f"cache_{quote(url, safe='')}_{param_hash}.json"

    def _cache_response(self, cache_file: Path, data: Dict[str, Any]) -> None:
        if not self.enable_cache:
            return
            
        try:
            cache_file.write_text(json.dumps(data, indent=2))
            self.logger.debug(f"Cached response to {cache_file}")
        except (IOError, TypeError) as e:
            self.logger.warning(f"Failed to cache response: {e}")

    def _load_cached_response(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        if not self.enable_cache:
            return None
            
        if not cache_file.exists():
            return None
            
        try:
            file_age = time.time() - cache_file.stat().st_mtime
            if file_age < self.config.cache_ttl:
                cached_data = json.loads(cache_file.read_text())
                self.logger.debug(f"Loaded cached response from {cache_file}")
                return cached_data
        except (IOError, json.JSONDecodeError) as e:
            self.logger.warning(f"Failed to load cached response from {cache_file}: {e}")
            
        return None

    def _make_request(self, url: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        if not self._validate_url(url):
            self.logger.error(f"Invalid URL: {url}")
            return None

        cache_file = None
        if self.enable_cache:
            cache_file = Path(self._get_cache_key(url, params))
            cached_data = self._load_cached_response(cache_file)
            if cached_data:
                return cached_data

        for attempt in range(self.config.retry_attempts):
            try:
                response = self.session.get(url, params=params, timeout=self.config.timeout)
                response.raise_for_status()
                data = response.json()
                
                if self.enable_cache and cache_file:
                    self._cache_response(cache_file, data)
                
                return data
                
            except requests.exceptions.Timeout:
                self.logger.warning(f"Request timeout for {url} (attempt {attempt + 1})")
                if attempt == self.config.retry_attempts - 1:
                    return None
                time.sleep(1)
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request failed for {url}: {e}")
                return None
            except ValueError as e:
                self.logger.error(f"JSON decode failed for {url}: {e}")
                return None
        
        return None

    def _validate_weather_data(self, data: WeatherData) -> bool:
        required_fields = ['temperature', 'description', 'source', 'city']
        
        for field in required_fields:
            if field not in data or data[field] is None:
                self.logger.warning(f"Missing required field '{field}' in weather data")
                return False
        
        try:
            float(data['temperature'])
            return True
        except (ValueError, TypeError):
            self.logger.warning(f"Invalid temperature value: {data['temperature']}")
            return False

    def get_open_meteo(self) -> Optional[WeatherData]:
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
                self.logger.error("Invalid response from Open-Meteo API")
                return None
            
            current = data['current']
            temperature = current.get('temperature_2m')
            if temperature is None:
                self.logger.error("Missing temperature in Open-Meteo response")
                return None
            
            weather_code = current.get('weather_code')
            description = self.open_meteo_weather_codes.get(weather_code, "Unknown")
            
            weather_data: WeatherData = {
                'temperature': float(temperature),
                'feels_like': float(current.get('apparent_temperature', temperature)),
                'humidity': float(current.get('relative_humidity_2m', 0)),
                'pressure': float(current.get('pressure_msl', 0)),
                'wind_speed': float(current.get('wind_speed_10m', 0)),
                'wind_direction': float(current.get('wind_direction_10m', 0)),
                'description': description,
                'source': 'Open-Meteo',
                'city': self.city
            }
            
            if self._validate_weather_data(weather_data):
                return weather_data
            return None
            
        except (ValueError, TypeError) as e:
            self.logger.error(f"Error processing Open-Meteo data: {e}")
            return None

    def get_weather_api(self) -> Optional[WeatherData]:
        try:
            url = "http://api.weatherapi.com/v1/current.json"
            params = {
                'key': self.weather_api_key,
                'q': self.city,
                'aqi': 'no'
            }
            
            data = self._make_request(url, params)
            if not data or 'current' not in data:
                self.logger.error("Invalid response from WeatherAPI")
                return None
            
            current = data['current']
            temperature = current.get('temp_c')
            if temperature is None:
                self.logger.error("Missing temperature in WeatherAPI response")
                return None
            
            weather_data: WeatherData = {
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
            
            if self._validate_weather_data(weather_data):
                return weather_data
            return None
            
        except (ValueError, TypeError) as e:
            self.logger.error(f"Error processing WeatherAPI data: {e}")
            return None

    def get_wttr_in(self) -> Optional[WeatherData]:
        try:
            encoded_city = quote(self.city)
            url = f"https://wttr.in/{encoded_city}"
            params = {'format': 'j1'}
            
            data = self._make_request(url, params)
            if not data or 'current_condition' not in data or not data['current_condition']:
                self.logger.error("Invalid response from wttr.in")
                return None
            
            current = data['current_condition'][0]
            temp_c = current.get('temp_C')
            if temp_c is None:
                self.logger.error("Missing temperature in wttr.in response")
                return None
            
            weather_data: WeatherData = {
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
            
            if self._validate_weather_data(weather_data):
                return weather_data
            return None
            
        except (ValueError, TypeError) as e:
            self.logger.error(f"Error processing wttr.in data: {e}")
            return None

    def get_all_weather_data(self) -> Dict[str, WeatherData]:
        results = {}
        
        api_functions = [
            ('Open-Meteo', self.get_open_meteo),
            ('wttr.in', self.get_wttr_in),
            ('WeatherAPI', self.get_weather_api)
        ]
        
        for name, api_func in api_functions:
            try:
                self.logger.info(f"Fetching data from {name}")
                result = api_func()
                if result:
                    results[name] = result
                    self.logger.info(f"Successfully retrieved data from {name}")
                else:
                    self.logger.warning(f"Failed to retrieve data from {name}")
            except Exception as e:
                self.logger.error(f"Unexpected error from {name}: {e}")
            
            time.sleep(self.config.request_delay)
        
        return results


def get_env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None:
        return default
    
    try:
        return float(value)
    except ValueError:
        logging.warning(f"Invalid float value for {key}: '{value}'. Using default: {default}")
        return default


def format_weather_report(results: Dict[str, WeatherData]) -> str:
    if not results:
        return "No weather data could be retrieved from any source.\n"
    
    separator = "=" * 40
    report = f"\n{results[next(iter(results))].get('city', 'WEATHER')} REPORT\n"
    report += f"{separator}\n"
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
    report += f"{separator}\n"
    
    return report


def main():
    print("Fetching weather data from free APIs...")
    
    city = os.getenv('WEATHER_CITY', 'Vilnius')
    lat = get_env_float('WEATHER_LAT', 54.6872)
    lon = get_env_float('WEATHER_LON', 25.2797)
    
    enable_cache_str = os.getenv('ENABLE_CACHE', 'False').lower()
    enable_cache = enable_cache_str in ('true', '1', 'yes', 'y')
    
    weather = FreeWeatherAPI(city=city, lat=lat, lon=lon, enable_cache=enable_cache)
    results = weather.get_all_weather_data()
    
    print(format_weather_report(results))


if __name__ == "__main__":
    main()
