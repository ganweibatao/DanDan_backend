from rest_framework import serializers
from .models import VocabularyBook, BookWord, StudentCustomization, WordBasic
import json # Import json for parsing meanings

class VocabularyBookSerializer(serializers.ModelSerializer):
    word_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = VocabularyBook
        fields = ['id', 'name', 'word_count', 'is_system_preset', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class WordBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = WordBasic
        fields = ['id', 'word', 'phonetic_symbol', 'uk_pronunciation', 'us_pronunciation', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class BookWordSerializer(serializers.ModelSerializer):
    # Explicitly define fields sourced from related models or derived
    word = serializers.CharField(source='word_basic.word', read_only=True)
    pronunciation = serializers.CharField(source='word_basic.phonetic_symbol', read_only=True, allow_null=True)
    # Derive translation from the meanings JSON field
    translation = serializers.SerializerMethodField()
    # Derive part_of_speech from the meanings JSON field
    part_of_speech = serializers.SerializerMethodField()
    example = serializers.CharField(source='example_sentence', read_only=True, allow_null=True)
    book_id = serializers.IntegerField(source='vocabulary_book_id', read_only=True)

    class Meta:
        model = BookWord
        # Update fields to include part_of_speech
        fields = [
            'id',
            'book_id',
            'word',
            'translation',
            'part_of_speech',
            'pronunciation',
            'example',
            'word_order',
            'created_at',
            'updated_at',
        ]

    def get_translation(self, obj):
        """
        Extracts the translation string from the meanings JSON based on the
        actual structure: [{"pos": "...", "meaning": "..."}].
        """
        meaning_obj = self._get_first_meaning_obj(obj)
        if meaning_obj and 'meaning' in meaning_obj:
            translation_text = meaning_obj['meaning']
            return str(translation_text) if translation_text is not None else None
        elif isinstance(meaning_obj, str) and meaning_obj == "Error parsing": # Check for error string
             return "Error parsing translation"
        return None

    def get_part_of_speech(self, obj):
        """
        Extracts the part of speech string from the meanings JSON based on the
        actual structure: [{"pos": "...", "meaning": "..."}].
        """
        meaning_obj = self._get_first_meaning_obj(obj)
        if meaning_obj and 'pos' in meaning_obj:
            pos_text = meaning_obj['pos']
            return str(pos_text) if pos_text is not None else None
        # Don't return error string here, just None if not found
        return None

    def _get_first_meaning_obj(self, obj):
        """
        Helper method to safely parse and return the first meaning object
        from the meanings field. Returns the object or None or "Error parsing".
        """
        if not obj.meanings:
            return None
        try:
            data_to_parse = obj.meanings
            if isinstance(obj.meanings, str):
                data_to_parse = json.loads(obj.meanings)

            if isinstance(data_to_parse, list) and len(data_to_parse) > 0:
                first_meaning_obj = data_to_parse[0]
                if isinstance(first_meaning_obj, dict):
                    return first_meaning_obj # Return the dictionary
            return None # Return None if not list or empty or first item not dict
        except (json.JSONDecodeError, TypeError, IndexError) as e:
            # print(f"Error parsing meanings for word ID {obj.id}: {e}")
            return "Error parsing" # Return specific error string

class StudentCustomizationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    word_spelling = serializers.CharField(source='word.word', read_only=True)
    
    class Meta:
        model = StudentCustomization
        fields = [
            'id', 'student', 'student_name', 'word', 'word_spelling',
            'chinese_meaning', 'example_sentence', 'created_at'
        ]
        read_only_fields = ['created_at']
        
class BookWordWithCustomizationSerializer(BookWordSerializer):
    """带有学生自定义内容的单词序列化器"""
    custom_chinese_meaning = serializers.SerializerMethodField()
    custom_example_sentence = serializers.SerializerMethodField()
    
    class Meta(BookWordSerializer.Meta):
        fields = BookWordSerializer.Meta.fields + ['custom_chinese_meaning', 'custom_example_sentence']
    
    def get_custom_chinese_meaning(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
            
        try:
            student = request.user.student
            customization = StudentCustomization.objects.filter(student=student, word=obj).first()
            return customization.chinese_meaning if customization else None
        except:
            return None
    
    def get_custom_example_sentence(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
            
        try:
            student = request.user.student
            customization = StudentCustomization.objects.filter(student=student, word=obj).first()
            return customization.example_sentence if customization else None
        except:
            return None 