import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin
import re
import csv

class CostaRicaJobsScraper:
    def __init__(self):
        self.base_url = "https://empleos.net"
        self.search_url = "https://empleos.net/buscar_vacantes.php"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
    def get_job_listings_page(self):
        """Get job listings from first page only"""
        params = {
            'Claves': '',
            'Area': '',
            'Pais': '1',  # Costa Rica
        }
        
        try:
            print(f"\nFetching first page...")
            response = self.session.get(self.search_url, params=params, timeout=30)
            response.raise_for_status()
            print(f"Response URL: {response.url}")
            time.sleep(3)
            return response.text
        except Exception as e:
            print(f"Error fetching page: {e}")
            return None
    
    def parse_job_listings_from_page(self, html):
        """Extract all job URLs from the listings page"""
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        job_urls = []
        
        job_links = soup.find_all('a', href=re.compile(r'/puesto/\d+'))
        print(f"Found {len(job_links)} job links")
        
        for link in job_links:
            href = link.get('href')
            if href:
                full_url = urljoin(self.base_url, href)
                if full_url not in job_urls:
                    job_urls.append(full_url)
        
        print(f"Total unique URLs extracted: {len(job_urls)}")
        return job_urls
    
    def get_job_details(self, job_url):
        """Scrape detailed job information from individual job page"""
        try:
            print(f"  Fetching: {job_url}")
            response = self.session.get(job_url, timeout=30)
            response.raise_for_status()
            
            time.sleep(2)
            
            # Detect the actual encoding from the response
            if response.encoding and response.encoding.lower() != 'utf-8':
                # If site declares non-UTF-8, decode using that then re-encode to UTF-8
                soup = BeautifulSoup(response.content, 'html.parser')
            else:
                # Otherwise use the text as-is
                soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract location first as it's used for address and map_location
            location_value = self.extract_location(soup)
            
            job_data = {
                '_job_featured_image': self.extract_featured_image(soup),
                '_job_title': self.extract_title(soup),
                '_job_featured': self.is_featured(soup),
                '_job_filled': 0,
                '_job_urgent': self.is_urgent(soup),
                '_job_description': self.extract_description(soup),
                '_job_category': self.extract_category(soup),
                '_job_type': self.extract_type(soup),
                '_job_tag': 'Costa Rica',
                '_job_expiry_date': self.calculate_expiry_date(),
                '_job_gender': self.extract_gender(soup),
                '_job_apply_type': 'external',
                '_job_apply_url': job_url,
                '_job_apply_email': self.extract_email(soup),
                '_job_salary_type': self.extract_salary_type(soup),
                '_job_salary': self.extract_salary(soup),
                '_job_max_salary': self.extract_salary(soup),
                '_job_experience': self.extract_experience(soup),
                '_job_career_level': self.extract_career_level(soup),
                '_job_qualification': self.extract_qualification(soup),
                '_job_video_url': self.extract_video(soup),
                '_job_photos': self.extract_photos(soup),
                '_job_application_deadline_date': self.extract_deadline(soup),
                '_job_address': location_value,
                '_job_location': location_value,
                '_job_map_location': location_value
            }
            
            return job_data
            
        except Exception as e:
            print(f"  ✗ Error getting job details: {e}")
            return None
    
    def extract_featured_image(self, soup):
        img = soup.find('img', class_=re.compile(r'logo|company', re.IGNORECASE))
        if img and img.get('src'):
            return urljoin(self.base_url, img['src'])
        return ''
    
    def extract_title(self, soup):
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            text = heading.get_text(strip=True)
            text = re.sub(r'Vacante\s+Fresca', '', text, flags=re.IGNORECASE).strip()
            if text and len(text) > 2:
                return self.clean_text(text)
        return ''
    
    def is_featured(self, soup):
        featured_badge = soup.find(class_=re.compile(r'featured|destacado', re.IGNORECASE))
        return 1 if featured_badge else 0
    
    def is_urgent(self, soup):
        urgent_badge = soup.find(text=re.compile(r'Vacante\s+Fresca|Urgente', re.IGNORECASE))
        return 1 if urgent_badge else 0
    
    def extract_description(self, soup):
        desc_section = soup.find(text=re.compile(r'Funciones del Puesto|Descripción', re.IGNORECASE))
        if desc_section:
            parent = desc_section.find_parent()
            if parent:
                desc_div = parent.find_next_sibling() or parent.parent
                if desc_div:
                    return self.clean_text(desc_div.get_text(separator='\n', strip=True))
        return ''
    
    def clean_text(self, text):
        """Clean and fix encoding issues - only fix the � symbol, keep original text"""
        if not text:
            return ''
        
        # Only replace the � replacement character that appears due to encoding mismatch
        # Map common Spanish accented characters that become �
        text = text.replace('�', 'ó')  # Most common case
        
        # If still has issues, try these specific patterns
        if '�' in text:
            # Try to detect what the � should be based on context
            text = text.replace('descripci�n', 'descripción')
            text = text.replace('Descripci�n', 'Descripción')
            text = text.replace('importaci�n', 'importación')
            text = text.replace('exportaci�n', 'exportación')
            text = text.replace('actuaci�n', 'actuación')
            text = text.replace('operaci�n', 'operación')
            text = text.replace('Corporaci�n', 'Corporación')
            text = text.replace('revisi�n', 'revisión')
            text = text.replace('Elaboraci�n', 'Elaboración')
            text = text.replace('t�cnico', 'técnico')
            text = text.replace('tem�tica', 'temática')
            text = text.replace('Acad�mico', 'Académico')
            text = text.replace('asesor�a', 'asesoría')
            text = text.replace('estad�stica', 'estadística')
            text = text.replace('�rea', 'Área')
            text = text.replace('Ubicaci�n', 'Ubicación')
            text = text.replace('as�', 'así')
            text = text.replace('G�nero', 'Género')
        
        return text.strip()
    
    def extract_category(self, soup):
        area_label = soup.find(text=re.compile(r'Área del Puesto', re.IGNORECASE))
        if area_label:
            parent = area_label.find_parent()
            if parent:
                value_elem = parent.find_next_sibling()
                if value_elem:
                    return self.clean_text(value_elem.get_text(strip=True))
        return ''
    
    def extract_type(self, soup):
        type_text = soup.find(text=re.compile(r'Tiempo Completo|Tiempo Parcial', re.IGNORECASE))
        if type_text:
            text = str(type_text).lower()
            if 'completo' in text:
                return 'Tiempo Completo'
            elif 'parcial' in text:
                return 'Tiempo Parcial'
        return 'Tiempo Completo'
    
    def calculate_expiry_date(self):
        expiry = datetime.now() + timedelta(days=90)
        return expiry.strftime('%Y-%m-%d')
    
    def extract_gender(self, soup):
        gender_text = soup.find(text=re.compile(r'Género|Gender|Sexo', re.IGNORECASE))
        if gender_text:
            parent = gender_text.find_parent()
            if parent:
                value = parent.find_next_sibling()
                if value:
                    text = value.get_text(strip=True).lower()
                    if 'masculino' in text:
                        return 'Masculino'
                    elif 'femenino' in text:
                        return 'Femenino'
        return 'Indistinto'
    
    def extract_email(self, soup):
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', soup.get_text())
        return emails[0] if emails else ''
    
    def extract_salary_type(self, soup):
        salary_text = soup.find(text=re.compile(r'Salario|Salary', re.IGNORECASE))
        if salary_text:
            text = str(salary_text.parent.get_text(strip=True)).lower()
            if 'mensual' in text:
                return 'Mensual'
            elif 'anual' in text:
                return 'Anual'
        return 'Mensual'
    
    def extract_salary(self, soup):
        salary_label = soup.find(text=re.compile(r'Salario', re.IGNORECASE))
        if salary_label:
            parent = salary_label.find_parent()
            if parent:
                salary_section = parent.find_next_sibling() or parent.parent
                if salary_section:
                    text = salary_section.get_text()
                    numbers = re.findall(r'\d+', text.replace(',', ''))
                    if numbers:
                        return numbers[0]
        return ''
    
    def extract_experience(self, soup):
        exp_text = soup.find(text=re.compile(r'Experiencia', re.IGNORECASE))
        if exp_text:
            parent = exp_text.find_parent()
            if parent:
                value = parent.find_next_sibling()
                if value:
                    return self.clean_text(value.get_text(strip=True))
        return ''
    
    def extract_career_level(self, soup):
        level_text = soup.find(text=re.compile(r'Nivel de Cómputo|Career Level', re.IGNORECASE))
        if level_text:
            parent = level_text.find_parent()
            if parent:
                value = parent.find_next_sibling()
                if value:
                    return self.clean_text(value.get_text(strip=True))
        return ''
    
    def extract_qualification(self, soup):
        qual_label = soup.find(text=re.compile(r'Nivel Académico', re.IGNORECASE))
        if qual_label:
            parent = qual_label.find_parent()
            if parent:
                value_elem = parent.find_next_sibling()
                if value_elem:
                    return self.clean_text(value_elem.get_text(strip=True))
        return ''
    
    def extract_video(self, soup):
        video = soup.find('iframe', src=re.compile(r'youtube|vimeo', re.IGNORECASE))
        return video['src'] if video else ''
    
    def extract_photos(self, soup):
        photos = []
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src and 'logo' not in src.lower():
                photos.append(urljoin(self.base_url, src))
        return ','.join(photos[:5])
    
    def extract_deadline(self, soup):
        deadline_text = soup.find(text=re.compile(r'Fecha\s+Límite|Deadline', re.IGNORECASE))
        if deadline_text:
            parent = deadline_text.find_parent()
            if parent:
                value = parent.find_next_sibling()
                if value:
                    date_text = value.get_text(strip=True)
                    try:
                        date_obj = datetime.strptime(date_text, '%d/%m/%Y')
                        return date_obj.strftime('%Y-%m-%d')
                    except:
                        pass
        return self.calculate_expiry_date()
    
    def extract_location(self, soup):
        loc_label = soup.find(text=re.compile(r'Ubicación del Puesto', re.IGNORECASE))
        if loc_label:
            parent = loc_label.find_parent()
            if parent:
                value_elem = parent.find_next_sibling()
                if value_elem:
                    loc_text = value_elem.get_text(strip=True)
                    if loc_text and len(loc_text) > 3:
                        return self.clean_text(loc_text)
        return 'Costa Rica'
    
    def scrape_first_page(self):
        """Scrape only the first page"""
        print("\n" + "="*60)
        print("SCRAPING FIRST PAGE - ~20 JOBS")
        print("="*60)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        html = self.get_job_listings_page()
        if not html:
            print("Failed to fetch first page")
            return []
        
        job_urls = self.parse_job_listings_from_page(html)
        all_jobs = []
        
        for i, job_url in enumerate(job_urls, 1):
            print(f"\n[{i}/{len(job_urls)}] Processing job...")
            job_data = self.get_job_details(job_url)
            if job_data:
                all_jobs.append(job_data)
                print(f"  ✓ Scraped: {job_data['_job_title']}")
            time.sleep(2)
        
        return all_jobs
    
    def save_to_json(self, jobs, filename='costa_rica_jobs.json'):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Saved {len(jobs)} jobs to {filename}")
    
    def save_to_csv(self, jobs, filename='costa_rica_jobs.csv'):
        if not jobs:
            return
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=jobs[0].keys())
            writer.writeheader()
            writer.writerows(jobs)
        print(f"✓ Saved {len(jobs)} jobs to {filename}")


if __name__ == "__main__":
    scraper = CostaRicaJobsScraper()
    jobs = scraper.scrape_first_page()
    
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    
    if jobs:
        scraper.save_to_json(jobs)
        scraper.save_to_csv(jobs)
        print(f"\n✅ Successfully scraped {len(jobs)} jobs from first page!")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("\n⚠️ No jobs were scraped")