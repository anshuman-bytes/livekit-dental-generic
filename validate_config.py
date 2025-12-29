#!/usr/bin/env python3
"""
Configuration Validator for Multi-Tenant Dental Agent

This script validates customer configuration files to ensure they have
all required fields and correct structure before deployment.

Usage:
    python validate_config.py test_configs/test-practice-config.json
    python validate_config.py --all  # Validate all configs in test_configs/
"""

import json
import sys
import os
import argparse
from typing import Dict, Any, List, Tuple


class ConfigValidator:
    """Validates customer configuration files"""
    
    # Required top-level fields
    REQUIRED_FIELDS = [
        'customer_id',
        'customer',
        'system_prompt',
        'consultation_types',
        'doctors',
        'azure_storage'
    ]
    
    # Required customer sub-fields
    REQUIRED_CUSTOMER_FIELDS = [
        'name',
        'phone'
    ]
    
    # Required azure_storage sub-fields
    REQUIRED_STORAGE_FIELDS = [
        'container',
        'folder'
    ]
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_json_syntax(self, file_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate JSON syntax.
        
        Returns:
            Tuple of (success, config_dict)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return True, config
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON syntax: {e}")
            return False, {}
        except FileNotFoundError:
            self.errors.append(f"File not found: {file_path}")
            return False, {}
    
    def validate_required_fields(self, config: Dict[str, Any]) -> bool:
        """Validate all required top-level fields are present"""
        valid = True
        
        for field in self.REQUIRED_FIELDS:
            if field not in config:
                self.errors.append(f"Missing required field: '{field}'")
                valid = False
        
        return valid
    
    def validate_customer_section(self, config: Dict[str, Any]) -> bool:
        """Validate customer section"""
        if 'customer' not in config:
            return False  # Already caught by required_fields
        
        customer = config['customer']
        valid = True
        
        if not isinstance(customer, dict):
            self.errors.append("'customer' must be an object/dict")
            return False
        
        for field in self.REQUIRED_CUSTOMER_FIELDS:
            if field not in customer:
                self.errors.append(f"Missing required customer field: '{field}'")
                valid = False
        
        # Validate phone format
        if 'phone' in customer:
            phone = customer['phone']
            if not isinstance(phone, str) or not phone.startswith('+'):
                self.warnings.append("Phone should be in international format (+44...)")
        
        return valid
    
    def validate_customer_id(self, config: Dict[str, Any]) -> bool:
        """Validate customer_id format"""
        if 'customer_id' not in config:
            return False
        
        customer_id = config['customer_id']
        valid = True
        
        if not isinstance(customer_id, str):
            self.errors.append("'customer_id' must be a string")
            return False
        
        if not customer_id:
            self.errors.append("'customer_id' cannot be empty")
            return False
        
        if not customer_id.islower():
            self.warnings.append("'customer_id' should be lowercase")
        
        if ' ' in customer_id:
            self.errors.append("'customer_id' cannot contain spaces (use hyphens)")
            valid = False
        
        if not customer_id.replace('-', '').replace('_', '').isalnum():
            self.warnings.append("'customer_id' should only contain letters, numbers, and hyphens")
        
        return valid
    
    def validate_system_prompt(self, config: Dict[str, Any]) -> bool:
        """Validate system prompt"""
        if 'system_prompt' not in config:
            return False
        
        prompt = config['system_prompt']
        valid = True
        
        if not isinstance(prompt, str):
            self.errors.append("'system_prompt' must be a string")
            return False
        
        if not prompt.strip():
            self.errors.append("'system_prompt' cannot be empty")
            return False
        
        if len(prompt) < 100:
            self.warnings.append("'system_prompt' is quite short (< 100 chars). Consider adding more detail.")
        
        if len(prompt) > 2000:
            self.warnings.append("'system_prompt' is very long (> 2000 chars). Consider shortening.")
        
        return valid
    
    def validate_consultation_types(self, config: Dict[str, Any]) -> bool:
        """Validate consultation types"""
        if 'consultation_types' not in config:
            return False
        
        types = config['consultation_types']
        valid = True
        
        if not isinstance(types, dict):
            self.errors.append("'consultation_types' must be an object/dict")
            return False
        
        if not types:
            self.errors.append("'consultation_types' cannot be empty")
            return False
        
        for key, value in types.items():
            if not isinstance(value, str):
                self.errors.append(f"Consultation type '{key}' must map to a string service ID")
                valid = False
        
        if len(types) < 3:
            self.warnings.append("Only {} consultation type(s) defined. Consider adding more.".format(len(types)))
        
        return valid
    
    def validate_doctors(self, config: Dict[str, Any]) -> bool:
        """Validate doctors section"""
        if 'doctors' not in config:
            return False
        
        doctors = config['doctors']
        valid = True
        
        if not isinstance(doctors, dict):
            self.errors.append("'doctors' must be an object/dict")
            return False
        
        if not doctors:
            self.errors.append("'doctors' cannot be empty")
            return False
        
        for doctor_id, doctor_info in doctors.items():
            if not isinstance(doctor_info, dict):
                self.errors.append(f"Doctor '{doctor_id}' info must be an object/dict")
                valid = False
                continue
            
            if 'name' not in doctor_info:
                self.errors.append(f"Doctor '{doctor_id}' missing 'name' field")
                valid = False
        
        return valid
    
    def validate_azure_storage(self, config: Dict[str, Any]) -> bool:
        """Validate Azure storage configuration"""
        if 'azure_storage' not in config:
            return False
        
        storage = config['azure_storage']
        valid = True
        
        if not isinstance(storage, dict):
            self.errors.append("'azure_storage' must be an object/dict")
            return False
        
        for field in self.REQUIRED_STORAGE_FIELDS:
            if field not in storage:
                self.errors.append(f"Missing azure_storage field: '{field}'")
                valid = False
        
        # Check folder doesn't start/end with slash
        if 'folder' in storage:
            folder = storage['folder']
            if folder.startswith('/') or folder.endswith('/'):
                self.warnings.append("'azure_storage.folder' should not start or end with '/'")
        
        return valid
    
    def validate_voice_settings(self, config: Dict[str, Any]) -> bool:
        """Validate voice configuration (optional but recommended)"""
        if 'voice' not in config:
            self.warnings.append("No 'voice' configuration found. Default voice will be used.")
            return True
        
        voice = config['voice']
        valid = True
        
        if not isinstance(voice, dict):
            self.warnings.append("'voice' should be an object/dict")
            return False
        
        # Check voice_id
        if 'voice_id' not in voice:
            self.warnings.append("'voice.voice_id' not specified")
        
        # Check settings ranges
        if 'settings' in voice and isinstance(voice['settings'], dict):
            settings = voice['settings']
            
            if 'stability' in settings:
                if not 0.0 <= settings['stability'] <= 1.0:
                    self.warnings.append("'voice.settings.stability' should be between 0.0 and 1.0")
            
            if 'similarity_boost' in settings:
                if not 0.0 <= settings['similarity_boost'] <= 1.0:
                    self.warnings.append("'voice.settings.similarity_boost' should be between 0.0 and 1.0")
            
            if 'speed' in settings:
                if not 0.5 <= settings['speed'] <= 1.5:
                    self.warnings.append("'voice.settings.speed' should be between 0.5 and 1.5")
        
        return valid
    
    def validate_config_file(self, file_path: str) -> bool:
        """
        Validate a complete configuration file.
        
        Returns:
            True if valid, False if errors found
        """
        self.errors = []
        self.warnings = []
        
        print(f"\n{'='*60}")
        print(f"Validating: {file_path}")
        print(f"{'='*60}\n")
        
        # Step 1: JSON syntax
        valid, config = self.validate_json_syntax(file_path)
        if not valid:
            self._print_results()
            return False
        
        print("✅ JSON syntax valid")
        
        # Step 2: Required fields
        if self.validate_required_fields(config):
            print("✅ All required fields present")
        
        # Step 3: Detailed validation
        self.validate_customer_id(config)
        self.validate_customer_section(config)
        self.validate_system_prompt(config)
        self.validate_consultation_types(config)
        self.validate_doctors(config)
        self.validate_azure_storage(config)
        self.validate_voice_settings(config)
        
        # Print results
        self._print_results()
        
        return len(self.errors) == 0
    
    def _print_results(self):
        """Print validation results"""
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   - {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ Configuration is valid! No errors or warnings.")
        elif not self.errors:
            print("\n✅ Configuration is valid (but has warnings)")
        else:
            print("\n❌ Configuration has errors and must be fixed")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Validate customer configuration files')
    parser.add_argument('config_file', nargs='?', help='Path to config file to validate')
    parser.add_argument('--all', action='store_true', help='Validate all configs in test_configs/')
    
    args = parser.parse_args()
    
    validator = ConfigValidator()
    
    if args.all:
        # Validate all configs in test_configs directory
        config_dir = 'test_configs'
        if not os.path.exists(config_dir):
            print(f"❌ Directory not found: {config_dir}")
            sys.exit(1)
        
        json_files = [f for f in os.listdir(config_dir) if f.endswith('.json')]
        
        if not json_files:
            print(f"❌ No JSON files found in {config_dir}/")
            sys.exit(1)
        
        print(f"Found {len(json_files)} configuration file(s) to validate\n")
        
        results = {}
        for json_file in json_files:
            file_path = os.path.join(config_dir, json_file)
            results[json_file] = validator.validate_config_file(file_path)
        
        # Summary
        print(f"\n{'#'*60}")
        print("# SUMMARY")
        print(f"{'#'*60}\n")
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for file_name, valid in results.items():
            status = "✅" if valid else "❌"
            print(f"{status} {file_name}")
        
        print(f"\nTotal: {passed}/{total} passed")
        
        sys.exit(0 if passed == total else 1)
    
    elif args.config_file:
        # Validate single file
        valid = validator.validate_config_file(args.config_file)
        sys.exit(0 if valid else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()







