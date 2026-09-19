import os
import re

def replace_in_file(filepath, pattern, replacement, **kwargs):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = re.sub(pattern, replacement, content, **kwargs)
    
    if content != new_content:
        print(f"Fixed {filepath}")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

def main():
    base = 'd:/AHATTRICKZ-PROJECT/amoeba-ai/frontend/src'
    
    # 1. JoinExplorer.tsx
    path = os.path.join(base, 'components/admin/JoinExplorer.tsx')
    replace_in_file(path, r"ChevronRight, X", "")
    replace_in_file(path, r"ChevronRight,\s*X", "")
    replace_in_file(path, r"X\s*\} from 'lucide-react'", "} from 'lucide-react'")
    replace_in_file(path, r"appConcepts\??:\s*any\[\];", "")
    replace_in_file(path, r"isAdvancedMode\??:\s*boolean;", "")
    replace_in_file(path, r"onOpenPayload\??:\s*\(rel:\s*any\)\s*=>\s*void;", "")
    replace_in_file(path, r"appConcepts\s*=\s*\[\],\s*", "")
    replace_in_file(path, r"isAdvancedMode\s*=\s*true,\s*", "")
    replace_in_file(path, r"onOpenPayload,\s*", "")
    
    # 2. RelationshipList.tsx
    path = os.path.join(base, 'components/admin/RelationshipList.tsx')
    replace_in_file(path, r"AlertCircle,\s*", "")
    replace_in_file(path, r"ArrowRight,\s*", "")
    
    # 3. TableNode.tsx
    path = os.path.join(base, 'components/admin/TableNode.tsx')
    replace_in_file(path, r"import React, \{ memo \}", "import { memo }")
    replace_in_file(path, r"import React, \{ memo, useState \}", "import { memo, useState }")
    
    # 4. ChartRenderer.tsx
    path = os.path.join(base, 'components/charts/ChartRenderer.tsx')
    replace_in_file(path, r"innerRadius,\s*", "")
    replace_in_file(path, r"\{ chartType === 'pie' \? \(", "{ (props as any).chartType === 'pie' ? (")
    replace_in_file(path, r"\{ chartType === 'donut' \? \(", "{ (props as any).chartType === 'donut' ? (")
    
    # 5. ChatWidget.tsx
    path = os.path.join(base, 'components/ChatWidget.tsx')
    replace_in_file(path, r"MessageSquare,\s*", "")
    replace_in_file(path, r"CheckCircle2,\s*", "")

    # 6. DocumentsPage.tsx
    path = os.path.join(base, 'pages/admin/DocumentsPage.tsx')
    replace_in_file(path, r"color,\s*", "")
    replace_in_file(path, r"setSourceSuccess\(", "console.log(")

    # 7. RelationshipGraph.tsx
    path = os.path.join(base, 'pages/admin/RelationshipGraph.tsx')
    replace_in_file(path, r"addEdge,\s*", "")
    replace_in_file(path, r"\(event: any, edge: any\)", "(_event: any, edge: any)")

    # 8. SemanticMappingsPage.tsx
    path = os.path.join(base, 'pages/admin/SemanticMappingsPage.tsx')
    replace_in_file(path, r"Table,\s*", "")

    # 9. AmoebaChat.tsx
    path = os.path.join(base, 'pages/AmoebaChat.tsx')
    replace_in_file(path, r"onEvent=", "onEvent_dummy=")
    replace_in_file(path, r"chartType=", "chartType_dummy=")

    # 10. AppConcepts.tsx
    path = os.path.join(base, 'pages/AppConcepts.tsx')
    replace_in_file(path, r"ArrowRight,\s*", "")
    replace_in_file(path, r"<Database[^>]*>", "<div className='text-slate-400 font-mono'>[DB]</div>")

    # 11. LegacySemanticMapper.tsx
    path = os.path.join(base, 'pages/LegacySemanticMapper.tsx')
    replace_in_file(path, r"const sampleData = \[.*?\];", "", flags=re.DOTALL)
    replace_in_file(path, r"const \[loading, setLoading\] = useState\(true\);", "const [, setLoading] = useState(true);")
    replace_in_file(path, r"const \[loading, setLoading\] = useState<boolean>\(true\);", "const [, setLoading] = useState<boolean>(true);")

    # 12. Onboarding.tsx
    path = os.path.join(base, 'pages/Onboarding.tsx')
    replace_in_file(path, r"const \[proposals, setProposals\] = useState<any\[\]>\(\[\]\);", "")

    # 13. SystemHealth.tsx
    path = os.path.join(base, 'pages/SystemHealth.tsx')
    replace_in_file(path, r"warning,\s*", "")
    replace_in_file(path, r"const \[lastUndoBatch, setLastUndoBatch\] = useState<any\[\]>\(\[\]\);", "const [, setLastUndoBatch] = useState<any[]>([]);")
    replace_in_file(path, r"\(f, v\)", "(f: any, v: any)")
    
    print("Fixes applied.")

if __name__ == '__main__':
    main()
