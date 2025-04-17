from rest_framework import serializers
from .models import VocabularyBook, BookWord, StudentCustomization, WordBasic
import json # Import json for parsing meanings
from apps.accounts.models import Student

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
    word_basic_id = serializers.IntegerField(source='word_basic.id', read_only=True)

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
            'word_basic_id',
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
    # student = serializers.PrimaryKeyRelatedField(read_only=True) # Kept read_only in Meta
    # word_basic = serializers.PrimaryKeyRelatedField(queryset=WordBasic.objects.all()) # Use PrimaryKeyRelatedField for writing
    word_spelling = serializers.CharField(source='word_basic.word', read_only=True) # Read from word_basic

    class Meta:
        model = StudentCustomization
        fields = [
            'id', 
            'student', # Keep student ID for reference, but set in view
            'word_basic', # Keep word_basic ID for reference and writing
            'word_spelling', # Read-only spelling
            'meanings', 
            'example_sentence', 
            'notes', # <-- 新增字段
            'created_at', 
            'updated_at' # <-- 新增字段
        ]
        read_only_fields = ['student', 'created_at', 'updated_at', 'word_spelling']
        extra_kwargs = {
            'word_basic': {'write_only': True} # Allow writing word_basic ID but don't include full object on read unless explicitly asked
        }
        
class BookWordWithCustomizationSerializer(BookWordSerializer):
    """带有学生自定义内容的单词序列化器 (建议重构)
    
    注意：此序列化器每次获取自定义字段都会查询数据库，效率较低。
    更好的方法是在视图中使用 prefetch_related 获取所有相关的 customization，
    然后在这里直接访问预取的数据。
    """
    # 尝试预取 customization 数据 (需要在视图中配合 prefetch_related)
    # customization = StudentCustomizationSerializer(read_only=True) # 假设视图已预取
    
    # 仍然使用 SerializerMethodField 作为后备或当前实现
    customization = serializers.SerializerMethodField(read_only=True)
    notes = serializers.SerializerMethodField(read_only=True)

    class Meta(BookWordSerializer.Meta):
        # 从 BookWordSerializer 继承字段，并添加新的自定义字段
        fields = BookWordSerializer.Meta.fields + ['customization', 'notes']
        # 如果 BookWordSerializer.Meta.fields 已经包含 customization 和 notes, 则不需要加了
        # fields = BookWordSerializer.Meta.fields 

    def get_customization(self, obj):
        # 这个方法旨在返回完整的自定义对象，如果存在的话
        request = self.context.get('request')
        if not request or not request.user.is_authenticated or not hasattr(request.user, 'student'):
            return None
            
        # 尝试从预取的数据中获取 (推荐方式)
        # 检查 obj 是否有关联的 student_customizations (如果使用了 prefetch_related)
        # prefetched_customizations = getattr(obj, 'student_customizations_prefetched', None)
        # if prefetched_customizations:
        #     # 假设 prefetch_related('student_customizations', queryset=StudentCustomization.objects.filter(student=request.user.student))
        #     # 理论上这里应该只有一个或零个
        #     customization = prefetched_customizations[0] if prefetched_customizations else None
        #     if customization:
        #        return StudentCustomizationSerializer(customization).data
        #     return None

        # 后备方式：单独查询 (效率较低)
        try:
            student = request.user.student
            # 确保 obj.word_basic 存在
            if not obj.word_basic:
                 return None
            customization = StudentCustomization.objects.filter(student=student, word_basic=obj.word_basic).first()
            return StudentCustomizationSerializer(customization).data if customization else None
        except AttributeError: # Handle cases where request.user might not have student
            return None
        except Student.DoesNotExist: # Handle cases where student profile doesn't exist
            return None

    def get_notes(self, obj):
        # 直接从 get_customization 返回的数据中提取 notes，避免重复查询
        customization_data = self.get_customization(obj)
        return customization_data.get('notes') if customization_data else None

    # 移除 get_custom_chinese_meaning 和 get_custom_example_sentence
    # 因为 get_customization 已经返回了包含这些信息的完整对象
    # 如果前端只需要特定的字段，可以让前端从 customization 对象中提取