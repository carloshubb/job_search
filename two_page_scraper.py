import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin, parse_qs, urlparse
import re
import os

class CostaRicaJobsScraper:
    def __init__(self):
        self.base_url = "https://empleos.net"
        self.search_url = "https://empleos.net/buscar_vacantes.php"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
    def get_job_listings_page(self, page=1):
        """Get job listings from a specific page"""
        params = {
            'Claves': '',
            'Area': '',
            'Pais': '1',  # Costa Rica
        }
        
        # Add pagination parameter - the correct parameter is 'pagelocales'
        if page > 1:
            params['pagelocales'] = page
        
        try:
            print(f"\nFetching page {page}...")
            print(f"Parameters: {params}")
            
            response = self.session.get(self.search_url, params=params, timeout=30)
            response.raise_for_status()
            print(f"Response URL: {response.url}")
            print(f"Response length: {len(response.text)} characters")
            
            # Debug: Check if URL actually changed
            if page > 1:
                if 'pagelocales' in response.url or f'pagelocales={page}' in response.url:
                    print(f"✓ Pagination parameter accepted: pagelocales={page}")
                else:
                    print(f"⚠️  WARNING: Pagination parameter NOT in URL!")
            
            time.sleep(3)  # Slow website - be respectful
            return response.text
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            return None
    
    def parse_job_listings_from_page(self, html):
        """Extract all job URLs from a listings page"""
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        job_urls = []
        
        # Method 1: Find all links with /puesto/ in href
        job_links = soup.find_all('a', href=re.compile(r'/puesto/\d+'))
        print(f"Found {len(job_links)} job links with /puesto/ pattern")
        
        # Debug: Print first few job IDs to check if they're different
        if job_links:
            sample_ids = []
            for link in job_links[:10]:  # Show first 10
                href = link.get('href')
                if href:
                    match = re.search(r'/puesto/(\d+)', href)
                    if match:
                        job_id = match.group(1)
                        sample_ids.append(job_id)
            print(f"Sample job IDs from this page: {sample_ids}")
        
        for link in job_links:
            href = link.get('href')
            if href:
                full_url = urljoin(self.base_url, href)
                if full_url not in job_urls:
                    job_urls.append(full_url)
        
        # Method 2: Look for specific job card classes
        job_cards = soup.find_all('div', class_=re.compile(r'job|vacancy|puesto|oferta', re.IGNORECASE))
        for card in job_cards:
            link = card.find('a', href=re.compile(r'/puesto/'))
            if link:
                href = link.get('href')
                full_url = urljoin(self.base_url, href)
                if full_url not in job_urls:
                    job_urls.append(full_url)
        
        # Remove duplicates while preserving order
        unique_urls = []
        seen = set()
        for url in job_urls:
            if url not in seen:
                unique_urls.append(url)
                seen.add(url)
        
        print(f"Total unique URLs extracted: {len(unique_urls)}")
        
        return unique_urls
    
    def check_if_more_pages(self, html):
        """Check if there are more pages to scrape and extract next page URL"""
        if not html:
            return False
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for "siguiente" or "next" link
        next_link = soup.find('a', text=re.compile(r'siguiente|next|>|»', re.IGNORECASE))
        if next_link and next_link.get('href'):
            print(f"Found next page link: {next_link.get('href')}")
            return True
        
        # Look for numbered pagination links
        pagination_links = soup.find_all('a', href=re.compile(r'Pag=\d+', re.IGNORECASE))
        if pagination_links:
            print(f"Found {len(pagination_links)} pagination links")
            for link in pagination_links:
                print(f"  - {link.get('href')}")
            return True
        
        # Check for any pagination container
        pagination = soup.find_all(['div', 'ul'], class_=re.compile(r'pag|page|navigation', re.IGNORECASE))
        if pagination:
            print(f"Found pagination container: {pagination}")
            return True
        
        print("No pagination indicators found")
        return False
    
    def get_job_details(self, job_url):
        """Scrape detailed job information from individual job page"""
        try:
            print(f"  Fetching: {job_url}")
            response = self.session.get(job_url, timeout=30)
            response.raise_for_status()
            
            time.sleep(2)  # Be respectful to the server
            
            # Use response.text as-is, let BeautifulSoup handle encoding
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract location first as it's used for address and map_location
            location_value = self.extract_location(soup)
            
            job_data = {
                '_job_featured_image': self.extract_featured_image(soup),
                '_job_title': self.extract_title(soup),
                '_job_featured': self.is_featured(soup),
                '_job_filled': 0,  # Default
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
            print(f"  ✗ Error getting job details from {job_url}: {e}")
            return None
    
    def extract_featured_image(self, soup):
        """Extract company logo or featured image"""
        # Look for company logo
        img = soup.find('img', class_=re.compile(r'logo|company', re.IGNORECASE))
        if img and img.get('src'):
            return urljoin(self.base_url, img['src'])
        
        # Look for any prominent image near the title
        title_area = soup.find(['h1', 'h2'])
        if title_area:
            nearby_img = title_area.find_parent().find('img')
            if nearby_img and nearby_img.get('src'):
                return urljoin(self.base_url, nearby_img['src'])
        
        return ''
    
    def extract_title(self, soup):
        """Extract job title with proper encoding"""
        # First try to find the main heading with the job title (e.g., "Miscelánea")
        # Look for h1, h2, or specific job title patterns
        title_candidates = []
        
        # Try h1, h2 tags first
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            text = heading.get_text(strip=True)
            # Remove badges like "Vacante Fresca"
            text = re.sub(r'Vacante\s+Fresca', '', text, flags=re.IGNORECASE).strip()
            if text and len(text) > 2:
                title_candidates.append(text)
        
        # The job title is usually the first significant heading
        if title_candidates:
            return self.clean_text(title_candidates[0])
        
        # Fallback: look for class patterns
        title = soup.find(class_=re.compile(r'title|puesto|job-title'))
        if title:
            text = title.get_text(strip=True)
            text = re.sub(r'Vacante\s+Fresca', '', text, flags=re.IGNORECASE)
            return self.clean_text(text.strip())
        
        return ''
    
    def is_featured(self, soup):
        """Check if job is featured - returns 1 or 0"""
        featured_badge = soup.find(class_=re.compile(r'featured|destacado', re.IGNORECASE))
        return 1 if featured_badge is not None else 0
    
    def is_urgent(self, soup):
        """Check if job is urgent - returns 1 or 0"""
        urgent_badge = soup.find(text=re.compile(r'Vacante\s+Fresca|Urgente', re.IGNORECASE))
        return 1 if urgent_badge is not None else 0
    
    def extract_description(self, soup):
        """Extract job description with proper encoding"""
        # Look for "Funciones del Puesto" section
        desc_section = soup.find(text=re.compile(r'Funciones del Puesto|Descripción', re.IGNORECASE))
        if desc_section:
            parent = desc_section.find_parent()
            if parent:
                # Get all text from the description area
                desc_div = parent.find_next_sibling() or parent.parent
                if desc_div:
                    text = desc_div.get_text(separator='\n', strip=True)
                    # Clean up any encoding issues
                    return self.clean_text(text)
        
        # Fallback: look for common description classes or sections
        for section_name in ['ACERCA DE LA VACANTE', 'Funciones', 'Descripción']:
            section = soup.find(text=re.compile(section_name, re.IGNORECASE))
            if section:
                parent = section.find_parent()
                if parent:
                    next_elem = parent.find_next_sibling()
                    if next_elem:
                        text = next_elem.get_text(separator='\n', strip=True)
                        return self.clean_text(text)
        
        return ''
    
    def clean_text(self, text):
        """Clean and fix encoding issues - replace � symbols with correct Spanish characters"""
        if not text:
            return ''
        
        # The � symbol appears when UTF-8 text is incorrectly read
        # We need to identify the pattern and fix it
        
        # Common patterns where � appears before certain letters
        # These are the actual Unicode characters that got mangled
        fixes = {
            # ó patterns
            'Descripci�n': 'Descripción',
            'importaci�n': 'importación',
            'exportaci�n': 'exportación',
            'actuaci�n': 'actuación',
            'operaci�n': 'operación',
            'Corporaci�n': 'Corporación',
            'revisi�n': 'revisión',
            
            # é patterns  
            't�cnicos': 'técnicos',
            't�cnicas': 'técnicas',
            't�cnica': 'técnica',
            'tem�tica': 'temática',
            'Acad�mico': 'Académico',
            
            # í patterns
            'asesor�a': 'asesoría',
            'estad�sticas': 'estadísticas',
            'Tibás': 'Tibás',
            
            # á patterns
            'as�': 'así',
            'Elaboraci�n': 'Elaboración',
            
            # Generic � to common Spanish characters (last resort)
            '�': 'ó',  # Most common
        }
        
        # Apply all fixes
        for wrong, correct in fixes.items():
            text = text.replace(wrong, correct)
        
        return text.strip()
    
    def extract_category(self, soup):
        """Extract job category/area (in Spanish)"""
        # Look for "Área del Puesto" section
        area_label = soup.find(text=re.compile(r'Área del Puesto', re.IGNORECASE))
        if area_label:
            # Find the next element that contains the actual category value
            parent = area_label.find_parent()
            if parent:
                # Look for the value in next sibling or within the same section
                value_elem = parent.find_next_sibling()
                if value_elem:
                    category_text = value_elem.get_text(strip=True)
                    if category_text:
                        return self.clean_text(category_text)
                
                # Alternative: look within the parent's next elements
                for elem in parent.find_next_siblings():
                    text = elem.get_text(strip=True)
                    if text and not text.startswith('Ubicación') and len(text) > 2:
                        return self.clean_text(text)
                        break
        
        # Try finding category near the title or in job details section
        category_section = soup.find('div', class_=re.compile(r'area|category'))
        if category_section:
            return self.clean_text(category_section.get_text(strip=True))
        
        return ''
    
    def extract_type(self, soup):
        """Extract job type (in Spanish)"""
        # Look for employment type
        type_text = soup.find(text=re.compile(r'Tiempo Completo|Tiempo Parcial|Full[-\s]?Time|Part[-\s]?Time', re.IGNORECASE))
        if type_text:
            text = type_text.get_text(strip=True) if hasattr(type_text, 'get_text') else str(type_text)
            text_lower = text.lower()
            if 'completo' in text_lower or 'full' in text_lower:
                return 'Tiempo Completo'
            elif 'parcial' in text_lower or 'medio' in text_lower or 'part' in text_lower:
                return 'Tiempo Parcial'
        return 'Tiempo Completo'  # Default
    
    def extract_tags(self, soup):
        """Extract job tags"""
        tags = []
        # Look for icons or badges that might indicate tags
        icons = soup.find_all('img', src=re.compile(r'icon|tag'))
        for icon in icons:
            alt_text = icon.get('alt', '').strip()
            if alt_text:
                tags.append(alt_text)
        return ','.join(tags) if tags else ''
    
    def calculate_expiry_date(self):
        """Calculate expiry date (3 months from now)"""
        expiry = datetime.now() + timedelta(days=90)
        return expiry.strftime('%Y-%m-%d')
    
    def extract_gender(self, soup):
        """Extract gender requirement (in Spanish)"""
        gender_text = soup.find(text=re.compile(r'Género|Gender|Sexo', re.IGNORECASE))
        if gender_text:
            parent = gender_text.find_parent()
            if parent:
                value = parent.find_next_sibling() or parent.find_next()
                if value:
                    text = value.get_text(strip=True).lower()
                    if 'masculino' in text or 'hombre' in text or 'male' in text:
                        return 'Masculino'
                    elif 'femenino' in text or 'mujer' in text or 'female' in text:
                        return 'Femenino'
                    elif 'indistinto' in text or 'ambos' in text or 'both' in text:
                        return 'Indistinto'
        return 'Indistinto'
    
    def extract_email(self, soup):
        """Extract application email"""
        # Look for email addresses
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, soup.get_text())
        return emails[0] if emails else ''
    
    def extract_salary_type(self, soup):
        """Extract salary type (in Spanish)"""
        salary_text = soup.find(text=re.compile(r'Salario|Salary|Sueldo', re.IGNORECASE))
        if salary_text:
            text = str(salary_text.parent.get_text(strip=True)).lower()
            if 'mensual' in text or 'monthly' in text or 'mes' in text:
                return 'Mensual'
            elif 'anual' in text or 'yearly' in text or 'año' in text:
                return 'Anual'
            elif 'hora' in text or 'hourly' in text:
                return 'Por Hora'
            elif 'semanal' in text or 'weekly' in text or 'semana' in text:
                return 'Semanal'
        return 'Mensual'
    
    def extract_salary(self, soup):
        """Extract minimum salary"""
        # Look for "Salario" section
        salary_label = soup.find(text=re.compile(r'Salario', re.IGNORECASE))
        if salary_label:
            parent = salary_label.find_parent()
            if parent:
                # Get all text in the salary section
                salary_section = parent.find_next_sibling() or parent.parent
                if salary_section:
                    text = salary_section.get_text()
                    # Extract just the number, removing commas and currency symbols
                    # Example: "350000 (Moneda Local)" -> "350000"
                    numbers = re.findall(r'\d+', text.replace(',', '').replace('.', ''))
                    if numbers:
                        return numbers[0]
        
        return ''
    
    def extract_max_salary(self, soup):
        """Extract maximum salary"""
        salary_text = soup.find(text=re.compile(r'Salario|Salary|Sueldo', re.IGNORECASE))
        if salary_text:
            parent = salary_text.find_parent()
            if parent:
                text = parent.get_text()
                # Look for salary range (e.g., "1000 - 2000")
                numbers = re.findall(r'\d+', text.replace(',', '').replace('.', ''))
                if len(numbers) >= 2:
                    return numbers[1]
        return ''
    
    def extract_experience(self, soup):
        """Extract experience requirement"""
        exp_text = soup.find(text=re.compile(r'Experiencia Deseada|Experiencia|Experience', re.IGNORECASE))
        if exp_text:
            parent = exp_text.find_parent()
            if parent:
                value = parent.find_next_sibling() or parent.find_next()
                if value:
                    return self.clean_text(value.get_text(strip=True))
        return ''
    
    def extract_career_level(self, soup):
        """Extract career level (in Spanish)"""
        # Look for "Nivel de Cómputo" or career level
        level_text = soup.find(text=re.compile(r'Nivel de Cómputo|Career Level|Nivel', re.IGNORECASE))
        if level_text:
            parent = level_text.find_parent()
            if parent:
                value = parent.find_next_sibling() or parent.find_next()
                if value:
                    text = value.get_text(strip=True)
                    # Keep it in Spanish as found
                    if text:
                        return self.clean_text(text)
        return ''
    
    def extract_qualification(self, soup):
        """Extract qualification/education requirement"""
        # Look for "Nivel Académico" section
        qual_label = soup.find(text=re.compile(r'Nivel Académico', re.IGNORECASE))
        if qual_label:
            parent = qual_label.find_parent()
            if parent:
                # Look for the value in the next sibling or nearby elements
                value_elem = parent.find_next_sibling()
                if value_elem:
                    qual_text = value_elem.get_text(strip=True)
                    if qual_text:
                        return self.clean_text(qual_text)
                
                # Alternative: check next elements
                for elem in parent.find_next_siblings():
                    text = elem.get_text(strip=True)
                    if text and len(text) > 2:
                        return self.clean_text(text)
                        break
        
        return ''
    
    def extract_video(self, soup):
        """Extract video URL if present"""
        video = soup.find('iframe', src=re.compile(r'youtube|vimeo', re.IGNORECASE))
        if video:
            return video['src']
        return ''
    
    def extract_photos(self, soup):
        """Extract additional photos"""
        photos = []
        images = soup.find_all('img')
        for img in images:
            src = img.get('src', '')
            if src and 'logo' not in src.lower() and 'icon' not in src.lower():
                full_url = urljoin(self.base_url, src)
                if full_url not in photos:
                    photos.append(full_url)
        return ','.join(photos[:5])  # Limit to 5 photos
    
    def extract_deadline(self, soup):
        """Extract application deadline"""
        deadline_text = soup.find(text=re.compile(r'Fecha[\s]+Límite|Deadline|Cierre', re.IGNORECASE))
        if deadline_text:
            parent = deadline_text.find_parent()
            if parent:
                value = parent.find_next_sibling() or parent.find_next()
                if value:
                    date_text = value.get_text(strip=True)
                    # Try to parse date
                    try:
                        # Handle format: dd/mm/yyyy
                        date_obj = datetime.strptime(date_text, '%d/%m/%Y')
                        return date_obj.strftime('%Y-%m-%d')
                    except:
                        pass
        return self.calculate_expiry_date()
    
    def extract_location(self, soup):
        """Extract location - used for address, location, and map_location"""
        # Look for "Ubicación del Puesto" section - this is the most reliable
        loc_label = soup.find(text=re.compile(r'Ubicación del Puesto', re.IGNORECASE))
        if loc_label:
            parent = loc_label.find_parent()
            if parent:
                # Look for the value in next sibling
                value_elem = parent.find_next_sibling()
                if value_elem:
                    loc_text = value_elem.get_text(strip=True)
                    # Full format: "Barrio Tournon, San Jose, Costa Rica"
                    if loc_text and len(loc_text) > 3:
                        return self.clean_text(loc_text)
                
                # Alternative: check nearby elements
                for elem in parent.find_next_siblings():
                    text = elem.get_text(strip=True)
                    # Look for text with commas (indicating location format)
                    if text and ',' in text and len(text) > 5:
                        return self.clean_text(text)
                        break
        
        # Look for location class
        location = soup.find(class_=re.compile(r'location|ubicacion'))
        if location:
            loc_text = location.get_text(strip=True)
            if loc_text:
                return self.clean_text(loc_text)
        
        # Look for location icon elements
        location_icons = soup.find_all('i', class_=re.compile(r'location|map|pin'))
        for icon in location_icons:
            sibling = icon.find_next_sibling()
            if sibling:
                loc_text = sibling.get_text(strip=True)
                if loc_text and len(loc_text) > 3:
                    return self.clean_text(loc_text)
        
        # Look for text patterns like "Barrio Tournon, San Jose, Costa Rica"
        location_pattern = soup.find(text=re.compile(r'[A-Z][a-záéíóúñ\s]+,\s*[A-Z][a-záéíóúñ\s]+,\s*Costa Rica', re.IGNORECASE))
        if location_pattern:
            return self.clean_text(location_pattern.strip())
        
        return 'Costa Rica'
    
    def scrape_all_pages(self, max_pages=44):
        """Scrape all job listings from all pages"""
        all_jobs = []
        all_job_ids = set()  # Track job IDs instead of URLs to avoid false duplicates
        page = 1
        
        # Store job IDs per page for debugging
        page_job_ids = {}
        
        while page <= max_pages:
            print(f"\n{'='*60}")
            print(f"PROCESSING PAGE {page}/{max_pages}")
            print(f"{'='*60}")
            
            html = self.get_job_listings_page(page)
            if not html:
                print(f"Failed to fetch page {page}, stopping...")
                break
            
            # Extract job URLs from this page
            job_urls = self.parse_job_listings_from_page(html)
            
            # Extract job IDs for comparison
            current_page_ids = []
            job_id_to_url = {}
            for url in job_urls:
                match = re.search(r'/puesto/(\d+)', url)
                if match:
                    job_id = match.group(1)
                    current_page_ids.append(job_id)
                    job_id_to_url[job_id] = url
            
            page_job_ids[page] = current_page_ids
            print(f"Job IDs on page {page}: {current_page_ids[:10]}...")
            
            print(f"Found {len(job_urls)} job URLs on page {page}")
            
            # Filter out jobs we've already scraped by ID
            new_job_ids = [job_id for job_id in current_page_ids if job_id not in all_job_ids]
            print(f"New unique job IDs: {len(new_job_ids)}")
            
            if not new_job_ids and page > 1:
                print("No new unique jobs found on this page, stopping...")
                print(f"\n📊 SUMMARY: Scraped {len(all_job_ids)} unique jobs total.")
                break
            
            # Add new job IDs to tracking set
            all_job_ids.update(new_job_ids)
            
            # Scrape each NEW job
            for i, job_id in enumerate(new_job_ids, 1):
                job_url = job_id_to_url[job_id]
                print(f"\n[{i}/{len(new_job_ids)}] Processing job ID {job_id}...")
                job_data = self.get_job_details(job_url)
                if job_data:
                    all_jobs.append(job_data)
                    print(f"  ✓ Scraped: {job_data['_job_title']}")
                time.sleep(2)  # Be respectful between requests
            
            # Check if there are more pages (but respect max_pages limit)
            if page >= max_pages:
                print(f"\nReached maximum page limit: {max_pages}")
                break
                
            has_more = self.check_if_more_pages(html)
            if not has_more:
                print(f"\nNo more pages found after page {page}")
                break
            
            page += 1
            print(f"\nTotal unique jobs scraped so far: {len(all_jobs)}")
            time.sleep(3)  # Longer delay between pages
        
        return all_jobs
    
    def scrape_first_page_only(self):
        """Scrape only the first page (for weekly updates)"""
        print("\n" + "="*60)
        print("SCRAPING FIRST PAGE ONLY (WEEKLY UPDATE)")
        print("="*60)
        return self.scrape_all_pages(max_pages=1)
    
    def scrape_two_pages(self):
        """Scrape first two pages only"""
        print("\n" + "="*60)
        print("SCRAPING FIRST TWO PAGES")
        print("="*60)
        return self.scrape_all_pages(max_pages=1)
    
    def save_to_json(self, jobs, filename='costa_rica_jobs.json'):
        """Save scraped jobs to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Saved {len(jobs)} jobs to {filename}")
    
    def save_to_csv(self, jobs, filename='costa_rica_jobs.csv'):
        """Save scraped jobs to CSV file with proper UTF-8 encoding"""
        import csv
        
        if not jobs:
            print("No jobs to save")
            return
        
        keys = jobs[0].keys()
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(jobs)
        print(f"✓ Saved {len(jobs)} jobs to {filename}")


def initial_scrape():
    """Run initial scrape of all 44 pages"""
    scraper = CostaRicaJobsScraper()
    print("\n" + "="*60)
    print("INITIAL SCRAPE - ALL PAGES")
    print("="*60)
    print("This may take a while due to respectful delays...")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    jobs = scraper.scrape_all_pages(max_pages=1)
    
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    
    if jobs:
        scraper.save_to_json(jobs, 'costa_rica_jobs_full.json')
        scraper.save_to_csv(jobs, 'costa_rica_jobs_full.csv')
        print(f"\n✅ Initial scrape complete!")
        print(f"Total jobs scraped: {len(jobs)}")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("\n⚠️ No jobs were scraped")
    
    return jobs


def weekly_update():
    """Run weekly update (first page only)"""
    scraper = CostaRicaJobsScraper()
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    jobs = scraper.scrape_first_page_only()
    
    print("\n" + "="*60)
    print("WEEKLY UPDATE COMPLETE")
    print("="*60)
    
    if jobs:
        # Load existing jobs
        existing_jobs = []
        if os.path.exists('costa_rica_jobs_full.json'):
            with open('costa_rica_jobs_full.json', 'r', encoding='utf-8') as f:
                existing_jobs = json.load(f)
            print(f"Loaded {len(existing_jobs)} existing jobs from file")
        
        # Add new jobs (avoiding duplicates by URL)
        existing_urls = {job['_job_apply_url'] for job in existing_jobs}
        new_jobs = [job for job in jobs if job['_job_apply_url'] not in existing_urls]
        
        if new_jobs:
            existing_jobs.extend(new_jobs)
            scraper.save_to_json(existing_jobs, 'costa_rica_jobs_full.json')
            scraper.save_to_csv(existing_jobs, 'costa_rica_jobs_full.csv')
            print(f"\n✅ Weekly update complete!")
            print(f"Added {len(new_jobs)} new jobs")
            print(f"Total jobs in database: {len(existing_jobs)}")
        else:
            print("\n✅ Weekly update complete!")
            print("No new jobs found")
            print(f"Total jobs in database: {len(existing_jobs)}")
    else:
        print("\n⚠️ No jobs were scraped in weekly update")
    
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return jobs


def scrape_two_pages_only():
    """Run scrape of first two pages only"""
    scraper = CostaRicaJobsScraper()
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    jobs = scraper.scrape_two_pages()
    
    print("\n" + "="*60)
    print("TWO-PAGE SCRAPE COMPLETE")
    print("="*60)
    
    if jobs:
        scraper.save_to_json(jobs, 'costa_rica_jobs_two_pages.json')
        scraper.save_to_csv(jobs, 'costa_rica_jobs_two_pages.csv')
        print(f"\n✅ Two-page scrape complete!")
        print(f"Total jobs scraped: {len(jobs)}")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("\n⚠️ No jobs were scraped")
    
    return jobs


def test_pagination():
    """Test function to check if pagination is working - shows job IDs from each page"""
    scraper = CostaRicaJobsScraper()
    
    print("\n" + "="*60)
    print("TESTING PAGINATION - Checking Job IDs")
    print("="*60)
    
    for page in [1, 2]:
        print(f"\n{'='*60}")
        print(f"CHECKING PAGE {page}")
        print(f"{'='*60}")
        
        html = scraper.get_job_listings_page(page)
        if html:
            job_urls = scraper.parse_job_listings_from_page(html)
            
            job_ids = []
            for url in job_urls:
                match = re.search(r'/puesto/(\d+)', url)
                if match:
                    job_ids.append(match.group(1))
            
            print(f"\nJob IDs found on page {page}:")
            print(f"Total: {len(job_ids)}")
            print(f"IDs: {job_ids}")
            print(f"\nSample URLs:")
            for i, url in enumerate(job_urls[:3], 1):
                print(f"  {i}. {url}")
        
        time.sleep(3)
    
    print("\n" + "="*60)
    print("PAGINATION TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    # CHOOSE ONE OF THE FOLLOWING OPTIONS:
    
    # Option 1: Scrape ONLY first 2 pages (DEFAULT)
    scrape_two_pages_only()
    
    # Option 2: Test pagination without full scraping (UNCOMMENT to test)
    # test_pagination()
    
    # Option 3: For initial scrape (all pages up to 44) - COMMENT OUT if not needed:
    # initial_scrape()
    
    # Option 4: For weekly updates (first page only) - COMMENT OUT if not needed:
    # weekly_update()