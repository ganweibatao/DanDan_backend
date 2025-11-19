from rest_framework import serializers
from .models import VocabularyBook, BookWord, WordBasic, StudentKnownWord
import json # Import json for parsing meanings
from apps.accounts.models import Student

class VocabularyBookSerializer(serializers.ModelSerializer):
    word_count = serializers.IntegerField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = VocabularyBook
        fields = ['id', 'name', 'word_count', 'is_system_preset', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'created_by']

class WordBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = WordBasic
        fields = ['id', 'word', 'phonetic_symbol', 'uk_pronunciation', 'us_pronunciation', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class BookWordSerializer(serializers.ModelSerializer):
    # 使用effective属性，优先返回自定义值
    word = serializers.SerializerMethodField()
    pronunciation = serializers.SerializerMethodField()
    # Derive translation from the effective meanings JSON field
    translation = serializers.SerializerMethodField()
    # Derive part_of_speech from the effective meanings JSON field
    part_of_speech = serializers.SerializerMethodField()
    example = serializers.CharField(source='example_sentence', read_only=True, allow_null=True)
    book_id = serializers.IntegerField(source='vocabulary_book_id', read_only=True)
    word_basic_id = serializers.IntegerField(source='word_basic.id', read_only=True)
    # 新增字段：表示是否被自定义过
    is_customized = serializers.ReadOnlyField()

    class Meta:
        model = BookWord
        # Update fields to include part_of_speech and is_customized
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
            'is_customized',
        ]
    
    def get_word(self, obj):
        """返回有效的单词拼写"""
        return obj.effective_word
    
    def get_pronunciation(self, obj):
        """返回有效的音标"""
        return obj.effective_phonetic

    def get_translation(self, obj):
        """
        Extracts the translation string from the effective meanings JSON based on the
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
        Extracts the part of speech string from the effective meanings JSON based on the
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
        from the effective meanings field. Returns the object or None or "Error parsing".
        """
        # 使用effective_meanings而不是原始meanings
        effective_meanings = obj.effective_meanings
        if not effective_meanings:
            return None
        try:
            data_to_parse = effective_meanings
            if isinstance(effective_meanings, str):
                data_to_parse = json.loads(effective_meanings)

            if isinstance(data_to_parse, list) and len(data_to_parse) > 0:
                first_meaning_obj = data_to_parse[0]
                if isinstance(first_meaning_obj, dict):
                    return first_meaning_obj # Return the dictionary
            return None # Return None if not list or empty or first item not dict
        except (json.JSONDecodeError, TypeError, IndexError) as e:
            # print(f"Error parsing meanings for word ID {obj.id}: {e}")
            return "Error parsing" # Return specific error string

class BookWordUpdateSerializer(serializers.ModelSerializer):
    """用于更新词库单词的序列化器 - 支持自定义字段"""
    word = serializers.SerializerMethodField()
    translation = serializers.SerializerMethodField()
    part_of_speech = serializers.SerializerMethodField()
    phonetic = serializers.SerializerMethodField()
    example = serializers.CharField(source='example_sentence', read_only=True, allow_null=True)

    class Meta:
        model = BookWord
        fields = ['word', 'translation', 'part_of_speech', 'phonetic', 'example']
    
    def get_word(self, obj):
        """返回有效的单词拼写"""
        return obj.effective_word
    
    def get_translation(self, obj):
        """返回有效的翻译"""
        meaning_obj = self._get_first_meaning_obj(obj)
        if meaning_obj and 'meaning' in meaning_obj:
            translation_text = meaning_obj['meaning']
            return str(translation_text) if translation_text is not None else None
        return None
    
    def get_part_of_speech(self, obj):
        """返回有效的词性"""
        meaning_obj = self._get_first_meaning_obj(obj)
        if meaning_obj and 'pos' in meaning_obj:
            pos_text = meaning_obj['pos']
            return str(pos_text) if pos_text is not None else None
        return None
    
    def get_phonetic(self, obj):
        """返回有效的音标"""
        return obj.effective_phonetic
    
    def _get_first_meaning_obj(self, obj):
        """获取第一个meaning对象的辅助方法"""
        effective_meanings = obj.effective_meanings
        if not effective_meanings:
            return None
        try:
            data_to_parse = effective_meanings
            if isinstance(effective_meanings, str):
                data_to_parse = json.loads(effective_meanings)

            if isinstance(data_to_parse, list) and len(data_to_parse) > 0:
                first_meaning_obj = data_to_parse[0]
                if isinstance(first_meaning_obj, dict):
                    return first_meaning_obj
            return None
        except (json.JSONDecodeError, TypeError, IndexError):
            return None

    def update(self, instance, validated_data):
        # 权限检查：禁止修改系统预设词库
        if instance.vocabulary_book and instance.vocabulary_book.is_system_preset:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("系统预设词库不允许修改")
        
        # 注意：validated_data现在是从请求中传入的数据，不是从SerializerMethodField获取的
        # 我们需要从self.initial_data中获取原始输入数据
        input_data = self.initial_data
        
        # 获取example_sentence数据
        example_sentence = input_data.get('example', None)
        
        # 使用自定义字段存储修改，保持WordBasic表不变
        if 'word' in input_data:
            instance.custom_word = input_data['word']
        
        if 'phonetic' in input_data:
            instance.custom_phonetic = input_data['phonetic']

        # 处理自定义释义
        if 'translation' in input_data or 'part_of_speech' in input_data:
            # 获取当前有效的meanings作为基础
            current_meanings = instance.effective_meanings or []
            if isinstance(current_meanings, str):
                try:
                    current_meanings = json.loads(current_meanings)
                except json.JSONDecodeError:
                    current_meanings = []
            
            if not isinstance(current_meanings, list):
                current_meanings = []

            # 确保至少有一个meaning条目
            if len(current_meanings) == 0:
                current_meanings.append({})
            
            # 更新第一个meaning条目
            if 'translation' in input_data:
                current_meanings[0]['meaning'] = input_data['translation']
            if 'part_of_speech' in input_data:
                current_meanings[0]['pos'] = input_data['part_of_speech']

            # 保存到custom_meanings字段
            instance.custom_meanings = current_meanings

        # 更新例句
        if example_sentence is not None:
            instance.example_sentence = example_sentence

        instance.save()
        return instance

class StudentKnownWordSerializer(serializers.ModelSerializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    word = serializers.PrimaryKeyRelatedField(queryset=WordBasic.objects.all())

    class Meta:
        model = StudentKnownWord
        fields = ['id', 'student', 'word', 'marked_at']
        read_only_fields = ['marked_at']

    def create(self, validated_data):
        # Prevent duplicate entries
        instance, created = StudentKnownWord.objects.get_or_create(**validated_data)
        return instance

class StudentKnownWordDetailSerializer(serializers.ModelSerializer):
    """返回已知单词详细信息的序列化器"""
    word_text = serializers.CharField(source='word.word', read_only=True)
    phonetic = serializers.CharField(source='word.phonetic_symbol', read_only=True)
    uk_pronunciation = serializers.CharField(source='word.uk_pronunciation', read_only=True)
    us_pronunciation = serializers.CharField(source='word.us_pronunciation', read_only=True)
    
    # 从对应词书中获取释义信息
    meaning = serializers.SerializerMethodField()
    part_of_speech = serializers.SerializerMethodField()
    example_sentence = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentKnownWord
        fields = ['id', 'student', 'word', 'word_text', 'phonetic', 'uk_pronunciation', 
                 'us_pronunciation', 'meaning', 'part_of_speech', 'example_sentence', 'marked_at']
        read_only_fields = ['marked_at']
    
    def get_meaning(self, obj):
        """从词书中获取释义"""
        book_id = self.context.get('book_id')
        if book_id:
            try:
                book_word = BookWord.objects.filter(
                    vocabulary_book_id=book_id,
                    word_basic=obj.word
                ).first()
                if book_word:
                    meaning_obj = self._get_first_meaning_obj(book_word)
                    if meaning_obj and 'meaning' in meaning_obj:
                        return meaning_obj['meaning']
            except Exception:
                pass
        return None
    
    def get_part_of_speech(self, obj):
        """从词书中获取词性"""
        book_id = self.context.get('book_id')
        if book_id:
            try:
                book_word = BookWord.objects.filter(
                    vocabulary_book_id=book_id,
                    word_basic=obj.word
                ).first()
                if book_word:
                    meaning_obj = self._get_first_meaning_obj(book_word)
                    if meaning_obj and 'pos' in meaning_obj:
                        return meaning_obj['pos']
            except:
                pass
        return None
    
    def get_example_sentence(self, obj):
        """从词书中获取例句"""
        book_id = self.context.get('book_id')
        if book_id:
            try:
                book_word = BookWord.objects.filter(
                    vocabulary_book_id=book_id,
                    word_basic=obj.word
                ).first()
                if book_word:
                    return book_word.example_sentence
            except:
                pass
        return None
    
    def _get_first_meaning_obj(self, book_word):
        """获取第一个meaning对象的辅助方法"""
        effective_meanings = book_word.effective_meanings
        if not effective_meanings:
            return None
        try:
            # 确保我们处理的是Python对象，而不是JSON字符串
            if isinstance(effective_meanings, str):
                try:
                    data_to_parse = json.loads(effective_meanings)
                except json.JSONDecodeError:
                    # 如果解析失败，返回None
                    return None
            else:
                data_to_parse = effective_meanings

            # 检查是否是有效的列表格式
            if isinstance(data_to_parse, list) and len(data_to_parse) > 0:
                first_meaning_obj = data_to_parse[0]
                if isinstance(first_meaning_obj, dict):
                    return first_meaning_obj
            return None
        except (TypeError, IndexError, AttributeError):
            return None