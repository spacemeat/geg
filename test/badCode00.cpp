#include <vector>

template <class T>
class Foo
{
    public:

    T bar;
};

int main(int argc, char** argv)
{
    Foo<char, int> foo;

    return "foo";
}
